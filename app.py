def process_tradingview_alert(email_body, subject, from_email):
    """پردازش آلرت TradingView"""
    try:
        logger.info(f"🎯 پردازش ایمیل: {subject}")
        
        # تشخیص نماد - الگوی بهبود یافته و دقیق
        symbol = "UNKNOWN"
        
        # الگوهای دقیق‌تر برای تشخیص نماد
        symbol_patterns = [
            # الگوی اصلی: BASE/QUOTE
            r'([A-Z]{2,10})[/](USDT|USDC|USD|BUSD)',
            # الگوی با خط فاصله
            r'([A-Z]{2,10})[-](USDT|USDC|USD|BUSD)',
            # الگوی با فضای خالی
            r'([A-Z]{2,10})\s+(USDT|USDC|USD|BUSD)',
            # الگوی معکوس: QUOTE/BASE
            r'(USDT|USDC|USD|BUSD)[/]([A-Z]{2,10})',
            # جستجو در کل متن برای نماد
            r'\b([A-Z]{2,10})(USDT|USDC|USD|BUSD)\b'
        ]
        
        for i, pattern in enumerate(symbol_patterns):
            symbol_match = re.search(pattern, subject.upper().replace(' ', ''))
            if symbol_match:
                logger.info(f"الگوی {i+1} matched: {symbol_match.groups()}")
                
                if i < 3:  # الگوهای BASE/QUOTE
                    base = symbol_match.group(1)
                    quote = symbol_match.group(2)
                    symbol = f"{base}/{quote}"
                elif i == 3:  # الگوی معکوس
                    quote = symbol_match.group(1)
                    base = symbol_match.group(2)
                    symbol = f"{base}/{quote}"
                else:  # الگوی یکپارچه
                    base = symbol_match.group(1)
                    quote = symbol_match.group(2)
                    symbol = f"{base}/{quote}"
                
                logger.info(f"✅ نماد تشخیص داده شد: {symbol}")
                break
        
        # اگر نماد تشخیص داده نشد، سعی کن از body ایمیل استخراج کن
        if symbol == "UNKNOWN":
            for pattern in symbol_patterns:
                symbol_match = re.search(pattern, email_body.upper().replace(' ', ''))
                if symbol_match:
                    # پردازش مشابه بالا
                    if pattern == symbol_patterns[3]:  # الگوی معکوس
                        quote = symbol_match.group(1)
                        base = symbol_match.group(2)
                        symbol = f"{base}/{quote}"
                    else:
                        base = symbol_match.group(1)
                        quote = symbol_match.group(2)
                        symbol = f"{base}/{quote}"
                    logger.info(f"✅ نماد از body تشخیص داده شد: {symbol}")
                    break
        
        # تشخیص قیمت کامل با اعشار
        price = "UNKNOWN"
        price_patterns = [
            r'[$]?(\d+\.\d{4,})',  # قیمت‌های با ۴ رقم اعشار یا بیشتر
            r'[$]?(\d+\.\d{2,})',  # قیمت‌های با ۲-۳ رقم اعشار
            r'[$]?(\d+\.\d+)',     # قیمت‌های با اعشار
            r'[$]?(\d+)'           # قیمت‌های بدون اعشار
        ]
        
        for pattern in price_patterns:
            price_match = re.search(pattern, subject)
            if price_match:
                price = price_match.group(1)
                logger.info(f"✅ قیمت تشخیص داده شد: {price}")
                break
        
        # اگر قیمت از subject پیدا نشد، از body جستجو کن
        if price == "UNKNOWN":
            for pattern in price_patterns:
                price_match = re.search(pattern, email_body)
                if price_match:
                    price = price_match.group(1)
                    logger.info(f"✅ قیمت از body تشخیص داده شد: {price}")
                    break
        
        # حجم معامله - غیرفعال شده چون در آلرت‌های TradingView معمولاً وجود ندارد
        volume = "ندارد"
        
        # تشخیص عمل معامله
        action = "ALERT"
        buy_keywords = ['CROSSING', 'ABOVE', 'CROSSED', 'BUY', 'LONG', 'خرید', 'بالا']
        sell_keywords = ['BELOW', 'SELL', 'SHORT', 'فروش', 'پایین']
        
        subject_upper = subject.upper()
        if any(word in subject_upper for word in buy_keywords):
            action = "BUY"
        elif any(word in subject_upper for word in sell_keywords):
            action = "SELL"
        
        logger.info(f"🔍 تشخیص نهایی: {action} {symbol} @ {price}")
        
        # ارسال به Telegram
        message = f"""🎯 <b>هشدار جدید از TradingView</b>

📈 <b>عمل:</b> {action}
💎 <b>نماد:</b> {symbol}
💰 <b>قیمت:</b> ${price}
📊 <b>حجم:</b> {volume}
🕒 <b>زمان:</b> {get_persian_datetime()}

📋 <i>موضوع: {subject}</i>"""
        
        success = send_telegram_message(message)
        if success:
            logger.info(f"✅ پیام ارسال شد: {action} {symbol} @ {price}")
            return True
        else:
            logger.error("❌ ارسال پیام ناموفق بود")
            return False
        
    except Exception as e:
        logger.error(f"❌ خطا در پردازش ایمیل: {e}")
        return False
