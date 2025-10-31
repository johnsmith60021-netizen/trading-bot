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
        
        # اتصال به Zoho
        mail = imaplib.IMAP4_SSL('imap.zoho.com', 993)
        mail.login(EMAIL, EMAIL_PASSWORD)
        mail.select('inbox')
        
        # پیدا کردن ایمیل‌های خوانده نشده
        status, messages = mail.search(None, 'UNSEEN')
        if status == 'OK':
            email_ids = messages[0].split()
            logger.info(f"📧 تعداد ایمیل‌های جدید: {len(email_ids)}")
            
            for email_id in email_ids:
                # دریافت ایمیل
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status == 'OK':
                    msg = email.message_from_bytes(msg_data[0][1])
                    subject = msg['subject']
                    from_email = msg['from']
                    
                    logger.info(f"📩 ایمیل جدید از: {from_email}")
                    logger.info(f"📝 موضوع: {subject}")
                    
                    # استخراج متن ایمیل
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/plain":
                                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                break
                    else:
                        body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                    
                    logger.info(f"📄 محتوای ایمیل: {body[:200]}...")
                    
                    # پردازش همه ایمیل‌ها (حتی اگر از TradingView نیستند)
                    process_tradingview_alert(body, subject, from_email)
        
        mail.close()
        mail.logout()
        
    except Exception as e:
        logger.error(f"❌ خطا در بررسی ایمیل: {e}")

def process_tradingview_alert(email_body, subject, from_email):
    """پردازش آلرت TradingView - نسخه بهبود یافته"""
    try:
        logger.info(f"🔍 پردازش ایمیل از: {from_email}")
        
        # تشخیص TradingView (مستقیم یا فوروارد)
        is_tradingview = any(domain in from_email.lower() for domain in [
            'noreply@tradingview.com',
            'tradingview.com',
            'alert@tradingview.com'
        ])
        
        if not is_tradingview:
            logger.warning(f"⚠️ ایمیل از منبع ناشناس: {from_email}")
            # حتی اگر از TradingView نیست، سعی کن اطلاعات رو استخراج کن
            logger.info("🔍 سعی در استخراج اطلاعات از ایمیل غیر TradingView...")
        
        # ترکیب موضوع و بدنه برای جستجو
        search_text = f"{subject} {email_body}"
        search_upper = search_text.upper()
        
        logger.info(f"🔍 متن جستجو: {search_text[:100]}...")
        
        # تشخیص عمل معامله
        action = "BUY" if "BUY" in search_upper else "SELL" if "SELL" in search_upper else "UNKNOWN"
        
        if action == "UNKNOWN":
            logger.warning("⚠️ عمل معامله تشخیص داده نشد")
            return

        # تشخیص نماد
        symbol = "BTC/USDT"
        for sym in ['XRP', 'BTC', 'ETH', 'ADA', 'DOT']:
            if sym in search_upper:
                symbol = f"{sym}/USDT"
                break
        
        # تشخیص مقدار
        amount = "100"
        amount_match = re.search(r'(\d+(?:\.\d+)?)\s*(USD|USDT|UNIT)?', search_upper)
        if amount_match:
            amount = amount_match.group(1)
        
        # ارسال به Telegram حتی اگر از TradingView نیست
        message = f"""🎯 <b>سیگنال جدید دریافت شد</b>

📈 <b>عمل:</b> {action}
💎 <b>نماد:</b> {symbol}
💰 <b>مقدار:</b> {amount}
🔍 <b>منبع:</b> {'TradingView' if is_tradingview else 'دیگر'}

📧 <i>فرستنده: {from_email}</i>
📋 <i>موضوع: {subject}</i>"""
        
        success = send_telegram_message(message)
        if success:
            logger.info(f"✅ پیام ارسال شد: {action} {symbol} از {from_email}")
        else:
            logger.error("❌ ارسال پیام ناموفق")
        
    except Exception as e:
        logger.error(f"❌ خطا در پردازش: {e}")

def email_checker_loop():
    """حلقه چک کردن ایمیل هر 30 ثانیه"""
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
        check_emails()
        return jsonify({"status": "success", "message": "بررسی ایمیل انجام شد"})
    except Exception as e:
        logger.error(f"خطا در تست: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "سیستم فعال است! ✅ از /test-full استفاده کنید"

# شروع چکر ایمیل
logger.info("🚀 راه‌اندازی سیستم TradingView Bot")
email_thread = threading.Thread(target=email_checker_loop, daemon=True)
email_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
