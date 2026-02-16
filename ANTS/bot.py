import telegram

def send_msg_telegram(telegram_token, telegram_id, msg):

    bot = telegram.Bot(telegram_token)
    bot.sendMessage(chat_id=telegram_id, text=msg)

    #return content