from os import environ

'''
The https url you got when you start ```ngrok```   
with the command ngrok ```ngrok http 8000 -host-header=localhost:8000```
'''
BOT_TOKEN = environ.get('BOT_TOKEN')
'''
The token you got from ```@BotFather``` on Telegram
'''
WEBHOOK_URL = '{domain}'+f'/webhook/{BOT_TOKEN}'
'''
Webhook url as ```{domain}/webhook/BOT_TOKEN``` 
'''
