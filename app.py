from flask import Flask, request, jsonify
import requests
import os
import logging
import imaplib
import email
import time
import threading
import re

app = Flask(__name__)

# تنظیمات Telegram
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# تنظیمات ایمیل - Outlook
EMAIL = os.getenv('EMAIL', 'your-email@outlook.com')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
IMAP_SERVER = 'outlook.office365.com'
IMAP_PORT = 993

def send_telegram_message(message):
    """ارسال پیام به Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"خطا در ارسال به Telegram: {e}")
        return False

def check_emails():
    """چک کردن ایمیل‌های جدید"""
    try:
        # اتصال به سرور ایمیل
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL, EMAIL_PASSWORD)
        mail.select('inbox')
        
        # جستجوی ایمیل‌های خوانده نشده
        status, messages = mail.search(None, 'UNSEEN')
        if status == 'OK':
            email_ids = messages[0].split()
            
            for email_id in email_ids:
                # دریافت ایمیل
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status == 'OK':
                    msg = email.message_from_bytes(msg_data[0][1])
                    subject = msg['subject']
                    from_email = msg['from']
                    
                    # پردازش متن ایمیل
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition"))
                            
                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = msg.get_payload(decode=True).decode()
                    
                    print(f"📧 ایمیل جدید از: {from_email}")
                    print(f"📝 موضوع: {subject}")
                    
                    # پردازش سیگنال TradingView
                    if "tradingview" in from_email.lower():
                        process_tradingview_alert(body, subject, from_email)
        
        mail.close()
        mail.logout()
        
    except Exception as e:
        print(f"❌ خطا در بررسی ایمیل: {e}")

def process_tradingview_alert(email_body, subject, from_email):
    """پردازش آلرت TradingView"""
    try:
        # استخراج اطلاعات از ایمیل
        action = "BUY" if "BUY" in subject.upper() else "SELL" if "SELL" in subject.upper() else "UNKNOWN"
        
        if action == "UNKNOWN":
            return
        
        # استخراج symbol و amount از متن ایمیل
        symbol = "BTC/USDT"
        amount = "100"
        
        # جستجو در متن ایمیل برای نماد و مقدار
        lines = email_body.split('\n')
        for line in lines:
            line_upper = line.upper()
            if any(sym in line_upper for sym in ['BTC', 'ETH', 'XRP', 'USDT']):
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.upper() in ['BTC', 'ETH', 'XRP'] and i+1 < len(parts):
                        if 'USDT' in parts[i+1].upper() or 'USD' in parts[i+1].upper():
                            symbol = f"{part.upper()}/USDT"
                    if part.isdigit() and float(part) > 0:
                        amount = part
        
        # ساخت پیام سیگنال
        signal_data = {
            "action": action,
            "symbol": symbol,
            "amount": amount,
            "source": "email",
            "subject": subject
        }
        
        print(f"🎯 پردازش سیگنال: {signal_data}")
        
        # ارسال به Telegram
        message = f"""🎯 سیگنال جدید از TradingView:

📈 عمل: {action}
💎 نماد: {symbol}
💰 مقدار: {amount}
📧 موضوع: {subject}
"""
        send_telegram_message(message)
        
        # TODO: بعداً اینجا معامله رو اجرا می‌کنیم
        
    except Exception as e:
        print(f"❌ خطا در پردازش ایمیل: {e}")
        send_telegram_message(f"❌ خطا در پردازش ایمیل: {str(e)}")

def email_checker_loop():
    """حلقه چک کردن ایمیل هر 30 ثانیه"""
    while True:
        try:
            check_emails()
        except Exception as e:
            print(f"خطا در چکر ایمیل: {e}")
        time.sleep(30)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        data = request.json
        print("📡 دریافت سیگنال:", data)
        
        message = f"🎯 سیگنال جدید از وب‌هوک:\n{data}"
        send_telegram_message(message)
        
        return jsonify({"status": "success", "message": "سیگنال دریافت شد"})
    
    except Exception as e:
        print(f"❌ خطا: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/test-email', methods=['GET'])
def test_email():
    """تست عملکرد ایمیل"""
    try:
        check_emails()
        return jsonify({"status": "success", "message": "بررسی ایمیل انجام شد"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "سرور فعال است! ✅ - سیستم ایمیل فعال شد"

# شروع چکر ایمیل در یک ترد جداگانه
email_thread = threading.Thread(target=email_checker_loop, daemon=True)
email_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
