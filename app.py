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
logger = logging.getLogger(__name__)

def get_persian_datetime():
    """دریافت تاریخ و زمان شمسی"""
    try:
        # استفاده از timezone محلی سرور
        now = datetime.now()
        
        # تبدیل به تاریخ شمسی
        persian_date = jdatetime.datetime.fromgregorian(
            datetime=now, 
            locale='fa_IR'
        )
        return persian_date.strftime('%Y/%m/%d %H:%M:%S')
    except Exception as e:
        logger.error(f"خطا در دریافت تاریخ شمسی: {e}")
        return "تاریخ نامعلوم"

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
        
        # تشخیص نماد - الگوی بهبود یافته و دقیق
        symbol = "UNKNOWN"
        
        # الگوهای دقیق‌تر برای تشخیص نماد
        symbol_patterns = [
            # الگوی اصلی: BASE/QUOTE
            r'([A-Z]{2,10})[/](USDT|USDC|USD|BUSD)',
            # الگوی با خط فاصله
            r'([A-Z]{2,10})[-](USDT|USDC|USD|BUSD)',
            # الگوی با فضای خالی
            r'([A-Z]{2,10})\s+(USDT|USDC|USD|BUSD)',
            # الگوی معکوس: QUOTE/BASE
            r'(USDT|USDC|USD|BUSD)[/]([A-Z]{2,10})',
            # جستجو در کل متن برای نماد
            r'\b([A-Z]{2,10})(USDT|USDC|USD|BUSD)\b'
        ]
        
        for i, pattern in enumerate(symbol_patterns):
            symbol_match = re.search(pattern, subject.upper().replace(' ', ''))
            if symbol_match:
                logger.info(f"الگوی {i+1} matched: {symbol_match.groups()}")
                
                if i < 3:  # الگوهای BASE/QUOTE
                    base = symbol_match.group(1)
                    quote = symbol_match.group(2)
                    symbol = f"{base}/{quote}"
                elif i == 3:  # الگوی معکوس
                    quote = symbol_match.group(1)
                    base = symbol_match.group(2)
                    symbol = f"{base}/{quote}"
                else:  # الگوی یکپارچه
                    base = symbol_match.group(1)
                    quote = symbol_match.group(2)
                    symbol = f"{base}/{quote}"
                
                logger.info(f"✅ نماد تشخیص داده شد: {symbol}")
                break
        
        # اگر نماد تشخیص داده نشد، سعی کن از body ایمیل استخراج کن
        if symbol == "UNKNOWN":
            for pattern in symbol_patterns:
                symbol_match = re.search(pattern, email_body.upper().replace(' ', ''))
                if symbol_match:
                    # پردازش مشابه بالا
                    if pattern == symbol_patterns[3]:  # الگوی معکوس
                        quote = symbol_match.group(1)
                        base = symbol_match.group(2)
                        symbol = f"{base}/{quote}"
                    else:
                        base = symbol_match.group(1)
                        quote = symbol_match.group(2)
                        symbol = f"{base}/{quote}"
                    logger.info(f"✅ نماد از body تشخیص داده شد: {symbol}")
                    break
        
        # تشخیص قیمت کامل با اعشار
        price = "UNKNOWN"
        price_patterns = [
            r'[$]?(\d+\.\d{4,})',  # قیمت‌های با ۴ رقم اعشار یا بیشتر
            r'[$]?(\d+\.\d{2,})',  # قیمت‌های با ۲-۳ رقم اعشار
            r'[$]?(\d+\.\d+)',     # قیمت‌های با اعشار
            r'[$]?(\d+)'           # قیمت‌های بدون اعشار
        ]
        
        for pattern in price_patterns:
            price_match = re.search(pattern, subject)
            if price_match:
                price = price_match.group(1)
                logger.info(f"✅ قیمت تشخیص داده شد: {price}")
                break
        
        # اگر قیمت از subject پیدا نشد، از body جستجو کن
        if price == "UNKNOWN":
            for pattern in price_patterns:
                price_match = re.search(pattern, email_body)
                if price_match:
                    price = price_match.group(1)
                    logger.info(f"✅ قیمت از body تشخیص داده شد: {price}")
                    break
        
        # حجم معامله - غیرفعال شده چون در آلرت‌های TradingView معمولاً وجود ندارد
        volume = "ندارد"
        
        # تشخیص عمل معامله
        action = "ALERT"
        buy_keywords = ['CROSSING', 'ABOVE', 'CROSSED', 'BUY', 'LONG', 'خرید', 'بالا']
        sell_keywords = ['BELOW', 'SELL', 'SHORT', 'فروش', 'پایین']
        
        subject_upper = subject.upper()
        if any(word in subject_upper for word in buy_keywords):
            action = "BUY"
        elif any(word in subject_upper for word in sell_keywords):
            action = "SELL"
        
        logger.info(f"🔍 تشخیص نهایی: {action} {symbol} @ {price}")
        
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
            logger.info(f"✅ پیام ارسال شد: {action} {symbol} @ {price}")
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
            processed = check_emails()
            if processed > 0:
                logger.info(f"✅ {processed} ایمیل جدید پردازش شد")
        except Exception as e:
            logger.error(f"خطا در چکر ایمیل: {e}")
        time.sleep(30)

def start_self_ping():
    """پینگ داخلی برای جلوگیری از خواب سریع"""
    def ping_loop():
        while True:
            try:
                response = requests.get("https://trading-bot-v6c3.onrender.com/health", timeout=10)
                logger.info("✅ پینگ داخلی ارسال شد")
            except Exception as e:
                logger.warning(f"⚠️ خطا در پینگ داخلی: {e}")
            time.sleep(120)  # هر ۲ دقیقه
    
    ping_thread = threading.Thread(target=ping_loop, daemon=True)
    ping_thread.start()

@app.route('/health')
def health_check():
    """Endpoint ساده برای cron-job.org"""
    return "OK", 200

@app.route('/ping')
def ping():
    """Endpoint برای نمایش وضعیت سرور"""
    return jsonify({
        "status": "active",
        "timestamp": get_persian_datetime(),
        "service": "TradingView Bot"
    }), 200

@app.route('/test-full', methods=['GET'])
def test_full():
    """تست کامل سیستم"""
    try:
        logger.info("🧪 شروع تست کامل سیستم")
        result = check_emails()
        return jsonify({
            "status": "success", 
            "message": f"بررسی ایمیل انجام شد. {result} ایمیل جدید پردازش شد.",
            "emails_processed": result,
            "timestamp": get_persian_datetime()
        })
    except Exception as e:
        logger.error(f"خطا در تست: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "service": "TradingView Bot",
        "timestamp": get_persian_datetime()
    })

# شروع سرویس‌ها - فقط در main
if __name__ == '__main__':
    logger.info("🚀 راه‌اندازی سیستم TradingView Bot")
    
    # شروع threadها فقط وقتی مستقیماً اجرا شود
    email_thread = threading.Thread(target=email_checker_loop, daemon=True)
    email_thread.start()
    
    start_self_ping()
    
    logger.info("✅ تمام سرویس‌ها راه‌اندازی شدند")
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
else:
    # برای زمانی که با gunicorn اجرا می‌شود
    logger.info("🚀 سیستم TradingView Bot با Gunicorn راه‌اندازی شد")
