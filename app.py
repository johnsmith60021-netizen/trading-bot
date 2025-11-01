def process_tradingview_alert(email_body, subject, from_email):
    """پردازش آلرت TradingView - با پشتیبانی کامل از تست"""
    try:
        logger.info(f"🎯 پردازش ایمیل: {subject}")
        
        # بررسی آیا این یک پیام تست است
        is_test_mode = any(marker in email_body for marker in ["TEST_MODE", "MANUAL_TEST", "این یک پیام تست است"])
        
        # پردازش پیام
        structured_data = parse_structured_alert(email_body, subject)
        
        if structured_data and structured_data.get('symbol') != "UNKNOWN":
            symbol = structured_data['symbol']
            action = structured_data['action']
            price = structured_data['price']
            volume = structured_data.get('volume', '1')
            condition = structured_data.get('condition', 'UNKNOWN')
            
            if is_test_mode:
                logger.info(f"🧪 پیام تست تشخیص داده شد: {action} {symbol} @ {price}")
                # برای پیام تست، مارک مشخص اضافه کنیم
                action = "TEST_" + action
            else:
                logger.info(f"✅ سیگنال واقعی: {action} {symbol} @ {price}")
                
        else:
            # پردازش قدیمی
            symbol, action, price, volume = parse_legacy_alert(email_body, subject)
            condition = "LEGACY_FORMAT"
        
        # ارسال به تلگرام
        message = create_telegram_message(action, symbol, price, volume, condition, is_test_mode)
        
        success = send_telegram_message(message)
        if success:
            log_msg = f"✅ پیام {'تست' if is_test_mode else 'واقعی'} ارسال شد: {action} {symbol} @ {price}"
            logger.info(log_msg)
            return True
        else:
            logger.error("❌ ارسال پیام ناموفق بود")
            return False
        
    except Exception as e:
        logger.error(f"❌ خطا در پردازش ایمیل: {e}")
        return False

def create_telegram_message(action, symbol, price, volume, condition, is_test_mode):
    """ایجاد پیام تلگرام با پشتیبانی از حالت تست"""
    
    if is_test_mode:
        # حذف پیشوند TEST_ از action برای نمایش تمیزتر
        clean_action = action.replace('TEST_', '')
        
        base_message = f"""🧪 <b>تست سیستم - سیگنال آزمایشی</b>

🎯 <b>وضعیت:</b> <code>TEST MODE</code>
📈 <b>عمل:</b> {clean_action}
💎 <b>نماد:</b> {symbol}
💰 <b>قیمت تست:</b> ${price}
📊 <b>حجم تست:</b> {volume}
🔄 <b>شرط:</b> {condition}

✅ <b>تاییدیه:</b> سیستم آلرت فعال است
📝 <b>یادداشت:</b> این یک پیام تست است"""
    
    else:
        base_message = f"""🎯 <b>سیگنال معاملاتی واقعی</b>

📈 <b>عمل:</b> {action}
💎 <b>نماد:</b> {symbol}
💰 <b>قیمت جاری:</b> ${price}
📊 <b>حجم:</b> {volume}
🔄 <b>شرط:</b> {condition}"""
    
    time_section = f"\n🕒 <b>زمان:</b> {get_persian_datetime()}"
    footer = "\n\n🔧 <i>سیستم معاملاتی خودکار</i>"
    
    return base_message + time_section + footer
