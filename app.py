from flask import Flask, request, jsonify
import requests
import os
import imaplib
import email
import time
import threading
import re
import logging

app = Flask(__name__)

# تنظیمات
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
EMAIL = os.getenv('EMAIL')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

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
        
        # پوشه صحیح: Notification (بدون s)
        target_folder = 'Notification'
        
        try:
            logger.info(f"📁 بررسی پوشه: {target_folder}")
            mail.select(target_folder)
            
            # جستجوی ایمیل‌های خوانده نشده
            status, messages = mail.search(None, 'UNSEEN')
            
            if status == 'OK':
                email_ids = messages[0].split()
                logger.info(f"📧 تعداد ایمیل‌های ناخوانده در {target_folder}: {len(email_ids)}")
                
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
                            process_tradingview_alert(body, subject, from_email)
                            
                            # ایمیل رو به عنوان خوانده شده علامت بزن
                            mail.store(email_id, '+FLAGS', '\\Seen')
                
            else:
                logger.error("❌ خطا در جستجوی ایمیل‌های ناخوانده")
                
        except Exception as e:
            logger.error(f"❌ مشکل در پوشه {target_folder}: {e}")
            return 0
        
        mail.logout()
        return len(email_ids) if status == 'OK' else 0
        
    except Exception as e:
        logger.error(f"❌ خطا در بررسی ایمیل: {e}")
        return 0

def process_tradingview_alert(email_body, subject, from_email):
    """پردازش آلرت TradingView"""
    try:
        logger.info(f"🎯 پردازش ایمیل جدید: {subject}")
        
        # تشخیص نماد
        symbol = "UNKNOWN"
        symbol_match = re.search(r'([A-Z]{2,10})(USDT|USDC|USD)', subject.upper())
        if symbol_match:
            base = symbol_match.group(1)
            quote = symbol_match.group(2)
            symbol = f"{base}/{quote}"
        
        # تشخیص قیمت
        price = "UNKNOWN"
        price_match = re.search(r'(\d+\.?\d*)', subject)
        if price_match:
            price = price_match.group(1)
        
        # تشخیص عمل معامله بر اساس نوع آلرت
        action = "ALERT"
        if any(word in subject.upper() for word in ['CROSSING', 'ABOVE', 'CROSSED']):
            action = "BUY"
        elif 'BELOW' in subject.upper():
            action = "SELL"
        
        logger.info(f"🔍 تشخیص: {action} {symbol} @ {price}")
        
        # ارسال به Telegram
        message = f"""🎯 <b>هشدار جدید از TradingView</b>

📈 <b>عمل:</b> {action}
💎 <b>نماد:</b> {symbol}
💰 <b>قیمت:</b> ${price}
✅ <b>وضعیت:</b> جدید

📋 <i>موضوع: {subject}</i>"""
        
        success = send_telegram_message(message)
        if success:
            logger.info(f"✅ پیام جدید ارسال شد: {action} {symbol} @ {price}")
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
        time.sleep(30)  # هر 30 ثانیه چک کن

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
logger.info("🚀 راه‌اندازی سیستم TradingView Bot - پوشه: Notification")
email_thread = threading.Thread(target=email_checker_loop, daemon=True)
email_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
