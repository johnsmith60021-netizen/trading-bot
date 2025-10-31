from flask import Flask
import os
import imaplib
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

@app.route('/test-simple')
def test_simple():
    try:
        email = os.getenv('EMAIL')
        password = os.getenv('EMAIL_PASSWORD')
        imap_server = os.getenv('IMAP_SERVER', 'outlook.office365.com')
        
        logger.info(f"🔧 Testing with: {email}, Server: {imap_server}")
        
        # تست اتصال
        mail = imaplib.IMAP4_SSL(imap_server, 993)
        mail.login(email, password)
        mail.select('inbox')
        
        status, messages = mail.search(None, 'UNSEEN')
        email_count = len(messages[0].split()) if status == 'OK' else 0
        
        mail.close()
        mail.logout()
        
        return f"✅ SUCCESS! Found {email_count} unread emails"
        
    except Exception as e:
        return f"❌ FAILED: {str(e)}"

@app.route('/')
def home():
    return "سیستم فعال - از /test-simple استفاده کنید"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
