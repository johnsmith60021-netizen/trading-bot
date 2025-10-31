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
EMAIL = os.getenv('EMAIL', 'john.smith60021@outlook.com')
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
        print("🔍 شروع بررسی ایمیل...")
        
        # اتصال به سرور ایمیل
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        print("✅ وصل شد به سرور ایمیل")
        
        mail.login(EMAIL, EMAIL_PASSWORD)
        print("✅ لاگین موفق")
        
        mail.select('inbox')
        print("✅ انتخاب صندوق ورودی")
        
        # جستجوی ایمیل‌های خوانده نشده
        status, messages = mail.search(None, 'UNSEEN')
        print(f"🔍 وضعیت جستجو: {status}")
        
        if status == 'OK':
            email_ids = messages[0].split()
            print(f"📧 تعداد ایمیل‌های جدید: {len(email_ids)}")
            
            for email_id in email_ids:
                print(f"📭 پردازش ایمیل ID: {email_id}")
                
                # دریافت ایمیل
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status == 'OK':
                    msg = email.message_from_bytes(msg_data[0][1])
                    subject = msg['subject']
                    from_email = msg['from']
                    
                    print(f"📩 از: {from_email}")
                    print(f"📝 موضوع: {subject}")
                    
                    # پردازش متن ایمیل
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition"))
                            
                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                break
                    else:
                        body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                    
                    print(f"📄 طول متن ایمیل: {len(body)} کاراکتر")
                    
                    # پردازش سیگنال TradingView
                    process_tradingview_alert(body, subject, from_email)
                else:
                    print(f"❌ خطا در دریافت ایمیل {email_id}")
        
        else:
            print("❌ خطا در جستجوی ایمیل‌ها")
        
        mail.close()
        mail.logout()
        print("✅ بررسی ایمیل تکمیل شد")
        
    except Exception as e:
        print(f"❌ خطا در بررسی ایمیل: {e}")
        send_telegram_message(f"❌ خطا در بررسی ایمیل: {str(e)}")

def process_tradingview_alert(email_body, subject, from_email):
    """پردازش آلرت TradingView - نسخه هوشمند"""
    try:
        print(f"🔍 شروع پردازش ایمیل از: {from_email}")
        
        # ترکیب موضوع و بدنه برای جستجو
        search_text = f"{subject} {email_body}"
        search_upper = search_text.upper()
        
        print(f"🔍 جستجو در متن: {search_text[:200]}...")
        
        # ۱. تشخیص عمل معامله
        action = "UNKNOWN"
        if "BUY" in search_upper or "خرید" in search_text:
            action = "BUY"
        elif "SELL" in search_upper or "فروش" in search_text:
            action = "SELL"
        
        print(f"🔍 عمل تشخیص داده شده: {action}")
        
        if action == "UNKNOWN":
            print("❌ عمل معامله مشخص نیست")
            return

        # ۲. تشخیص خودکار نماد (هر نمادی)
        symbol = "BTC/USDT"  # پیش‌فرض
        
        # الگوهای مختلف برای نمادها
        symbol_patterns = [
            r'([A-Z]{2,10})/?([A-Z]{3,6})',  # BTC/USDT, ETH/USDC
            r'([A-Z]{2,10})(USDT|USDC|BUSD|DAI)',  # BTCUSDT, ETHUSDC
            r'([A-Z]{2,10})/?(USD|EUR|GBP)',  # BTC/USD, ETHUSD
        ]
        
        for pattern in symbol_patterns:
            matches = re.finditer(pattern, search_upper)
            for match in matches:
                base_currency = match.group(1)
                quote_currency = match.group(2) if match.lastindex >= 2 else "USDT"
                
                # فیلتر کردن کلمات کلیدی نادرست
                if base_currency not in ['ALERT', 'TRADINGVIEW', 'BUY', 'SELL']:
                    symbol = f"{base_currency}/{quote_currency}"
                    print(f"🔍 نماد تشخیص داده شده: {symbol}")
                    break
            if symbol != "BTC/USDT":
                break

        # ۳. تشخیص مقدار
        amount = "100"  # پیش‌فرض
        
        # الگوهای مختلف برای مقادیر
        amount_patterns = [
            r'(\d+(?:\.\d+)?)\s*(USD|USDT|UNIT|COIN)',  # 100 USD, 0.5 USDT
            r'(\d+(?:\.\d+)?)\s*\$',  # 100 $
            r'amount[:\s]*(\d+(?:\.\d+)?)',  # amount: 100
            r'quantity[:\s]*(\d+(?:\.\d+)?)',  # quantity: 0.5
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, search_upper)
            if match:
                amount = match.group(1)
                print(f"🔍 مقدار تشخیص داده شده: {amount}")
                break

        # ۴. تشخیص اگر TradingView هست
        is_tradingview = any(domain in from_email.lower() for domain in [
            'tradingview.com', 'noreply@tradingview'
        ])

        # ساخت پیام سیگنال
        signal_data = {
            "action": action,
            "symbol": symbol,
            "amount": amount,
            "source": "tradingview" if is_tradingview else "other"
        }
        
        print(f"🎯 پردازش سیگنال کامل: {signal_data}")
        
        # ارسال به Telegram
        message = f"""🎯 سیگنال جدید از TradingView:

📈 عمل: {action}
💎 نماد: {symbol}
💰 مقدار: {amount}
🔍 منبع: {'تأیید شده' if is_tradingview else 'غیر مستقیم'}
📧 فرستنده: {from_email}

📋 متن اصلی:
{search_text[:200]}...
"""
        success = send_telegram_message(message)
        print(f"📤 ارسال به Telegram: {'موفق' if success else 'ناموفق'}")
        
    except Exception as e:
        print(f"❌ خطا در پردازش ایمیل: {e}")
        send_telegram_message(f"❌ خطا در پردازش ایمیل: {str(e)}")

def email_checker_loop():
    """حلقه چک کردن ایمیل هر 30 ثانیه"""
    print("🔄 شروع حلقه بررسی ایمیل...")
    while True:
        try:
            check_emails()
        except Exception as e:
            print(f"❌ خطا در چکر ایمیل: {e}")
        print("⏳ خواب به مدت 30 ثانیه...")
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
        print("🧪 شروع تست دستی ایمیل...")
        check_emails()
        return jsonify({"status": "success", "message": "بررسی ایمیل انجام شد"})
    except Exception as e:
        print(f"❌ خطا در تست ایمیل: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "سرور فعال است! ✅ - سیستم ایمیل فعال شد"

# شروع چکر ایمیل در یک ترد جداگانه
print("🚀 راه‌اندازی سیستم ایمیل...")
email_thread = threading.Thread(target=email_checker_loop, daemon=True)
email_thread.start()
print("✅ چکر ایمیل راه‌اندازی شد")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
