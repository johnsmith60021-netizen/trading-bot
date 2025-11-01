from flask import Flask, request, jsonify
import requests
import os
import imaplib
import email
import time
import threading
import re
import logging
from datetime import datetime
import jdatetime  # برای تاریخ شمسی

app = Flask(__name__)

# تنظیمات
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
EMAIL = os.getenv('EMAIL')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

def get_persian_datetime():
    """دریافت تاریخ و زمان شمسی"""
    now = datetime.now()
    persian_date = jdatetime.datetime.fromgregorian(datetime=now)
    return persian_date.strftime('%Y/%m/%d %H:%M:%S')

def send_telegram_message(message):
    """ارسال پیام به Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"خطا در ارسال Telegram: {e}")
        return False

def check_emails():
    """چک کردن و پردازش ایمیل‌های جدید"""
    try:
        logger.info("🔍 در حال بررسی ایمیل‌های جدید...")
        
        mail = imaplib.IMAP4_SSL('imap.zoho.com', 993)
        mail.login(EMAIL, EMAIL_PASSWORD)
        
        # بررسی هر دو پوشه
        folders = ['Notification', 'INBOX']
        total_processed = 0
        
        for folder in folders:
            try:
                logger.info(f"📁 بررسی پوشه: {folder}")
                mail.select(folder)
                
                # جستجوی ایمیل‌های خوانده نشده
                status, messages = mail.search(None, 'UNSEEN')
                
                if status == 'OK':
                    email_ids = messages[0].split()
                    logger.info(f"📧 تعداد ایمیل‌های ناخوانده در {folder}: {len(email_ids)}")
                    
                    folder_processed = 0
                    for email_id in email_ids:
                        status, msg_data = mail.fetch(email_id, '(RFC822)')
                        if status == 'OK':
                            msg = email.message_from_bytes(msg_data[0][1])
                            subject = msg['subject'] or "بدون موضوع"
                            from_email = msg['from']
                            
                            if "tradingview.com" in from_email.lower():
                                logger.info(f"🎯 ایمیل TradingView پیدا شد: {subject}")
                                
                                # استخراج متن ایمیل
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        if part.get_content_type() == "text/plain":
                                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                            break
                                else:
                                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                                
                                # پردازش ایمیل
                                if process_tradingview_alert(body, subject, from_email):
                                    folder_processed += 1
                                    # حذف ایمیل پس از پردازش موفق
                                    mail.store(email_id, '+FLAGS', '\\Deleted')
                    
                    # حذف دائمی ایمیل‌های علامت‌گذاری شده
                    if folder_processed > 0:
                        mail.expunge()
                    
                    total_processed += folder_processed
                    logger.info(f"✅ {folder_processed} ایمیل از {folder} پردازش و حذف شد")
                
            except Exception as e:
                logger.warning(f"⚠️ مشکل در پوشه {folder}: {e}")
                continue
        
        mail.logout()
        logger.info(f"🎉 پردازش کامل. مجموعاً {total_processed} ایمیل جدید پردازش و حذف شد.")
        return total_processed
        
    except Exception as e:
        logger.error(f"❌ خطا در بررسی ایمیل: {e}")
        return 0

def process_tradingview_alert(email_body, subject, from_email):
    """پردازش آلرت TradingView"""
    try:
        logger.info(f"🎯 پردازش ایمیل: {subject}")
        
        # تشخیص نماد
        symbol = "UNKNOWN"
        symbol_match = re.search(r'([A-Z]{2,10})[/\-\s](USDT|USDC|USD)', subject.upper())
        if symbol_match:
            base = symbol_match.group(1)
            quote = symbol_match.group(2)
            symbol = f"{base}/{quote}"
        
        # تشخیص قیمت کامل با اعشار
        price = "UNKNOWN"
        # الگوی بهبود یافته برای تشخیص اعداد اعشاری کامل
        price_match = re.search(r'(\d+\.\d+|\d+)', subject)
        if price_match:
            price = price_match.group(1)
        
        # تشخیص حجم معامله
        volume = "0"  # مقدار پیش‌فرض
        volume_match = re.search(r'volume\s*:\s*(\d+\.?\d*)', email_body.lower())
        if volume_match:
            volume = volume_match.group(1)
        else:
            # جستجوی الگوهای دیگر برای حجم
            volume_patterns = [
                r'vol\s*:\s*(\d+\.?\d*)',
                r'volume\s*=\s*(\d+\.?\d*)',
                r'amount\s*:\s*(\d+\.?\d*)'
            ]
            for pattern in volume_patterns:
                match = re.search(pattern, email_body.lower())
                if match:
                    volume = match.group(1)
                    break
        
        # تشخیص عمل معامله
        action = "ALERT"
        if any(word in subject.upper() for word in ['CROSSING', 'ABOVE', 'CROSSED', 'BUY', 'LONG']):
            action = "BUY"
        elif any(word in subject.upper() for word in ['BELOW', 'SELL', 'SHORT']):
            action = "SELL"
        
        logger.info(f"🔍 تشخیص: {action} {symbol} @ {price} حجم: {volume}")
        
        # ارسال به Telegram
        message = f"""🎯 <b>هشدار جدید از TradingView</b>

📈 <b>عمل:</b> {action}
💎 <b>نماد:</b> {symbol}
💰 <b>قیمت:</b> ${price}
📊 <b>حجم:</b> {volume}
🕒 <b>زمان:</b> {get_persian_datetime()}

📋 <i>موضوع: {subject}</i>"""
        
        success = send_telegram_message(message)
        if success:
            logger.info(f"✅ پیام ارسال شد: {action} {symbol} @ {price} حجم: {volume}")
            return True
        else:
            logger.error("❌ ارسال پیام ناموفق بود")
            return False
        
    except Exception as e:
        logger.error(f"❌ خطا در پردازش ایمیل: {e}")
        return False

def email_checker_loop():
    """حلقه چک کردن ایمیل"""
    logger.info("🔄 شروع حلقه بررسی ایمیل")
    while True:
        try:
            check_emails()
        except Exception as e:
            logger.error(f"خطا در چکر ایمیل: {e}")
        time.sleep(30)

@app.route('/test-full', methods=['GET'])
def test_full():
    """تست کامل سیستم"""
    try:
        logger.info("🧪 شروع تست کامل سیستم")
        result = check_emails()
        return jsonify({
            "status": "success", 
            "message": f"بررسی ایمیل انجام شد. {result} ایمیل جدید پردازش شد.",
            "emails_processed": result
        })
    except Exception as e:
        logger.error(f"خطا در تست: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "سیستم فعال است! ✅ از /test-full استفاده کنید"

# شروع چکر ایمیل
logger.info("🚀 راه‌اندازی سیستم TradingView Bot - پوشه‌ها: Notification, INBOX")
email_thread = threading.Thread(target=email_checker_loop, daemon=True)
email_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
