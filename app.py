from flask import Flask, request, jsonify
import requests
import os
import logging

app = Flask(__name__)

# تنظیمات Telegram
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', 'YOUR_CHAT_ID')

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

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        data = request.json
        print("📡 دریافت سیگنال:", data)
        
        # ارسال به Telegram
        message = f"🎯 سیگنال جدید:\n{data}"
        send_telegram_message(message)
        
        return jsonify({"status": "success", "message": "سیگنال دریافت شد"})
    
    except Exception as e:
        print(f"❌ خطا: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/telegram', methods=['POST'])
def handle_telegram():
    """دریافت پیام از Telegram"""
    data = request.json
    print("📱 پیام از Telegram:", data)
    return jsonify({"status": "ok"})

@app.route('/')
def home():
    return "سرور فعال است! ✅"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
