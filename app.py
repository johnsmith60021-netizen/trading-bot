from flask import Flask
import os
import imaplib
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

@app.route('/test-zoho')
def test_zoho():
    try:
        email = os.getenv('EMAIL')
        password = os.getenv('EMAIL_PASSWORD')
        
        logger.info(f"🔧 Testing Zoho with: {email}")
        
        # اتصال به Zoho - بدون نیاز به متغیرهای اضافه
        mail = imaplib.IMAP4_SSL('imap.zoho.com', 993)
        mail.login(email, password)
        mail.select('inbox')
        
        status, messages = mail.search(None, 'UNSEEN')
        email_count = len(messages[0].split()) if status == 'OK' else 0
        
        mail.close()
        mail.logout()
        
        return f"✅ ZOHO SUCCESS! Found {email_count} unread emails"
        
    except Exception as e:
        return f"❌ ZOHO FAILED: {str(e)}"

@app.route('/')
def home():
    return "سیستم فعال - از /test-zoho استفاده کنید"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
