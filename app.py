from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.json
    print("📡 دریافت سیگنال:", data)
    return jsonify({"status": "success", "message": "سیگنال دریافت شد"})

@app.route('/')
def home():
    return "سرور فعال است! ✅"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
