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
import jdatetime
import pytz

app = Flask(__name__)

# تنظیمات
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
EMAIL = os.getenv('EMAIL')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_persian_datetime():
    """دریافت تاریخ و زمان شمسی با تایم‌زون تهران"""
    try:
        # استفاده از UTC و اضافه کردن افست تهران
        utc_now = datetime.utcnow()
        tehran_offset = 3.5 * 60 * 60  # 3.5 ساعت به ثانیه
        tehran_time = utc_now.timestamp() + tehran_offset
        now_tehran = datetime.fromtimestamp(tehran_time)
        
        # تبدیل به تاریخ شمسی
        persian_date = jdatetime.datetime.fromgregorian(datetime=now_tehran, locale='fa_IR')
        return persian_date.strftime('%Y/%m/%d %H:%M:%S')
    except Exception as e:
        logger.error(f"خطا در دریافت تاریخ شمسی: {e}")
        return datetime.now().strftime('%Y/%m/%d %H:%M:%S')

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
        
        folders = ['Notification', 'INBOX']
        total_processed = 0
        
        for folder in folders:
            try:
                logger.info(f"📁 بررسی پوشه: {folder}")
                mail.select(folder)
                
                status, messages = mail.search(None, 'UNSEEN')
                
                if status == 'OK':
                    email_ids = messages[0].split()
                    logger.info(f"📧 ایمیل‌های ناخوانده: {len(email_ids)}")
                    
                    folder_processed = 0
                    for email_id in email_ids:
                        status, msg_data = mail.fetch(email_id, '(RFC822)')
                        if status == 'OK':
                            msg = email.message_from_bytes(msg_data[0][1])
                            subject = msg['subject'] or "بدون موضوع"
                            from_email = msg['from']
                            
                            if "tradingview.com" in from_email.lower():
                                logger.info(f"🎯 ایمیل TradingView: {subject}")
                                
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        if part.get_content_type() == "text/plain":
                                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                            break
                                else:
                                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                                
                                if process_tradingview_alert(body, subject, from_email):
                                    folder_processed += 1
                                    mail.store(email_id, '+FLAGS', '\\Deleted')
                    
                    if folder_processed > 0:
                        mail.expunge()
                    
                    total_processed += folder_processed
                    logger.info(f"✅ {folder_processed} ایمیل از {folder} پردازش شد")
                
            except Exception as e:
                logger.warning(f"⚠️ مشکل در پوشه {folder}: {e}")
                continue
        
        mail.logout()
        logger.info(f"🎉 پردازش کامل. {total_processed} ایمیل جدید.")
        return total_processed
        
    except Exception as e:
        logger.error(f"❌ خطا در بررسی ایمیل: {e}")
        return 0

def parse_structured_alert(email_body):
    """پردازش پیام ساختاریافته"""
    try:
        # الگو برای فرمت ساختاریافته
        pattern = r'([A-Z_]+):([^|]+)'
        matches = re.findall(pattern, email_body)
        
        if matches:
            data = dict(matches)
            return {
                'symbol': data.get('SYMBOL', 'UNKNOWN'),
                'action': data.get('ACTION', 'ALERT'),
                'price': data.get('PRICE', 'UNKNOWN'),
                'volume': data.get('VOLUME', 'ندارد'),
                'condition': data.get('CONDITION', 'UNKNOWN'),
                'is_test': 'TEST_MODE' in email_body or 'MANUAL_TEST' in data.get('CONDITION', '')
            }
        return None
    except Exception as e:
        logger.error(f"خطا در پردازش ساختاریافته: {e}")
        return None

def parse_legacy_alert(subject, body):
    """پردازش پیام قدیمی"""
    try:
        # تشخیص نماد
        symbol = "UNKNOWN"
        symbol_patterns = [
            r'([A-Z]{2,10})[/](USDT|USDC|USD|BUSD)',
            r'([A-Z]{2,10})[-](USDT|USDC|USD|BUSD)',
            r'\b([A-Z]{2,10})(USDT|USDC|USD|BUSD)\b'
        ]
        
        for pattern in symbol_patterns:
            match = re.search(pattern, subject.upper().replace(' ', ''))
            if match:
                if '/' in pattern or '-' in pattern:
                    symbol = f"{match.group(1)}/{match.group(2)}"
                else:
                    symbol = f"{match.group(1)}/{match.group(2)}"
                break
        
        # تشخیص قیمت
        price = "UNKNOWN"
        price_match = re.search(r'(\d+\.\d+|\d+)', subject)
        if price_match:
            price = price_match.group(1)
        
        # تشخیص عمل
        action = "ALERT"
        if any(word in subject.upper() for word in ['CROSSING', 'ABOVE', 'CROSSED', 'BUY']):
            action = "BUY"
        elif any(word in subject.upper() for word in ['BELOW', 'SELL']):
            action = "SELL"
        
        return symbol, action, price, 'ندارد'
        
    except Exception as e:
        logger.error(f"خطا در پردازش قدیمی: {e}")
        return "UNKNOWN", "ALERT", "UNKNOWN", "ندارد"

def process_tradingview_alert(email_body, subject, from_email):
    """پردازش آلرت TradingView"""
    try:
        logger.info(f"🎯 پردازش ایمیل: {subject}")
        
        # پردازش پیام ساختاریافته
        structured_data = parse_structured_alert(email_body)
        
        if structured_data and structured_data['symbol'] != "UNKNOWN":
            symbol = structured_data['symbol']
            action = structured_data['action']
            price = structured_data['price']
            volume = structured_data['volume']
            is_test = structured_data['is_test']
        else:
            # پردازش قدیمی
            symbol, action, price, volume = parse_legacy_alert(subject, email_body)
            is_test = "TEST" in subject.upper()
        
        if is_test:
            logger.info(f"🧪 پیام تست: {action} {symbol} @ {price}")
            action = "TEST_" + action
        else:
            logger.info(f"✅ سیگنال واقعی: {action} {symbol} @ {price}")
        
        # ایجاد و ارسال پیام
        message = create_telegram_message(action, symbol, price, volume, is_test)
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

def create_telegram_message(action, symbol, price, volume, is_test):
    """ایجاد پیام تلگرام"""
    if is_test:
        clean_action = action.replace('TEST_', '')
        base_message = f"""🧪 <b>تست سیستم - سیگنال آزمایشی</b>

🎯 <b>وضعیت:</b> TEST MODE
📈 <b>عمل:</b> {clean_action}
💎 <b>نماد:</b> {symbol}
💰 <b>قیمت تست:</b> ${price}
📊 <b>حجم:</b> {volume}"""
    else:
        base_message = f"""🎯 <b>سیگنال معاملاتی</b>

📈 <b>عمل:</b> {action}
💎 <b>نماد:</b> {symbol}
💰 <b>قیمت:</b> ${price}
📊 <b>حجم:</b> {volume}"""
    
    time_section = f"\n🕒 <b>زمان:</b> {get_persian_datetime()}"
    return base_message + time_section

def email_checker_loop():
    """حلقه چک کردن ایمیل"""
    logger.info("🔄 شروع حلقه بررسی ایمیل")
    while True:
        try:
            check_emails()
        except Exception as e:
            logger.error(f"خطا در چکر ایمیل: {e}")
        time.sleep(30)

def start_self_ping():
    """پینگ داخلی"""
    def ping_loop():
        while True:
            try:
                requests.get("https://trading-bot-v6c3.onrender.com/health", timeout=10)
                logger.info("✅ پینگ داخلی ارسال شد")
            except Exception as e:
                logger.warning(f"⚠️ خطا در پینگ داخلی: {e}")
            time.sleep(120)
    
    threading.Thread(target=ping_loop, daemon=True).start()

@app.route('/health')
def health_check():
    """Endpoint برای cron-job.org"""
    return "OK", 200

@app.route('/ping')
def ping():
    """Endpoint وضعیت سرور"""
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

# راه‌اندازی سرویس‌ها
if __name__ == '__main__':
    logger.info("🚀 راه‌اندازی سیستم TradingView Bot")
    
    # شروع threadها
    threading.Thread(target=email_checker_loop, daemon=True).start()
    start_self_ping()
    
    logger.info("✅ تمام سرویس‌ها راه‌اندازی شدند")
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
else:
    logger.info("🚀 سیستم با Gunicorn راه‌اندازی شد")
