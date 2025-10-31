from flask import Flask, request, jsonify
import requests
import os
import imaplib
import email
import sys

app = Flask(__name__)

# لاگ کردن به stdout
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
EMAIL = os.getenv('EMAIL')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

logger.info("🚀 APPLICATION STARTED - LOGGING WORKS!")
logger.info(f"📧 Email: {EMAIL}")
logger.info(f"🔑 Pass set: {'YES' if EMALE_PASSWORD else 'NO'}")

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
        response = requests.post(url, json=payload)
        return True
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

@app.route('/test-debug', methods=['GET'])
def test_debug():
    logger.info("🔍 DEBUG TEST STARTED")
    
    try:
        # تست IMAP
        logger.info("🔗 Connecting to IMAP...")
        mail = imaplib.IMAP4_SSL('outlook.office365.com', 993)
        logger.info("✅ IMAP Connected")
        
        mail.login(EMAIL, EMAIL_PASSWORD)
        logger.info("✅ Login successful")
        
        mail.select('inbox')
        logger.info("✅ Inbox selected")
        
        status, messages = mail.search(None, 'UNSEEN')
        email_count = len(messages[0].split()) if status == 'OK' else 0
        logger.info(f"📧 Unread emails: {email_count}")
        
        mail.close()
        mail.logout()
        
        # تست Telegram
        telegram_ok = send_telegram_message("🧪 تست دیباگ - سیستم فعال است")
        logger.info(f"📱 Telegram test: {'OK' if telegram_ok else 'FAILED'}")
        
        return jsonify({
            "status": "success",
            "imap": "connected", 
            "emails": email_count,
            "telegram": "sent"
        })
        
    except Exception as e:
        logger.error(f"❌ TEST FAILED: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def home():
    logger.info("📍 Home page accessed")
    return "سیستم فعال است - از /test-debug استفاده کنید"

if __name__ == '__main__':
    logger.info("🎯 Starting Flask application...")
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=True)
