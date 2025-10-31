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
