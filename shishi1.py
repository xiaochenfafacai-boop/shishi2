import os
import re
import json
import sqlite3
import logging
import pytz
import telebot
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

# --- 核心配置 ---
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get('TELEGRAM_TOKEN', '8965619504:AAEE9tcwcd1rhAkhPV97Wmdw4qlM-Qqi7Ow')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'https://shishi-777gg.onrender.com')
PORT = int(os.environ.get('PORT', 5000))
FOUNDER_USERS = [8179896441]
bot = telebot.TeleBot(TOKEN)
flask_app = Flask(__name__)

# --- 数据库连接池 ---
def get_db():
    conn = sqlite3.connect('bot_data.db', check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

# --- 修复后的核心记账逻辑 ---
@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    if message.chat.type == "private":
        return # 私聊逻辑保持不变

    gid = message.chat.id
    text = message.text.strip()
    username = message.from_user.first_name
    
    # 记账正则修复：兼容 +1000, +1000/7.3, 项目+1000, 项目+1000/7.3
    # 匹配规则：允许备注在前面或没有备注，支持汇率指定
    inc_pattern = re.compile(r'^(.*?)([\+\-])(\d+(?:\.\d+)?)(?:/(\d+(?:\.\d+)?))?$')
    match = inc_pattern.match(text)
    
    if match:
        remark = match.group(1).strip() or "普通入款"
        sign = match.group(2)
        amount = float(match.group(3))
        if sign == '-': amount = -amount
        rate = float(match.group(4)) if match.group(4) else 7.2
        
        # 执行入库
        usdt = amount / rate if amount > 0 else amount
        conn = get_db()
        conn.execute("INSERT INTO bills (group_id, remark, amount, usdt_amount, username, date_str) VALUES (?,?,?,?,?,?)",
                     (gid, remark, amount, usdt, username, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ 已记入: {remark} | {amount} RMB (汇率:{rate})")
        return

    # 下发记账
    if text.startswith("下发"):
        try:
            amt = float(re.findall(r"\d+\.?\d*", text)[0])
            conn = get_db()
            conn.execute("INSERT INTO bills (group_id, remark, usdt_amount, bill_type, username) VALUES (?,?,?,?,?)",
                         (gid, "下发", amt, "expense", username))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"📤 已下发: {amt} U")
        except:
            bot.reply_to(message, "❌ 下发格式错误，请使用: 下发 500")

# --- Webhook与服务启动 ---
@flask_app.route('/' + TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode('utf-8'))])
    return "ok", 200

if __name__ == '__main__':
    # 确保数据库表存在
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS bills 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, remark TEXT, 
         amount REAL, usdt_amount REAL, username TEXT, date_str TEXT, bill_type TEXT DEFAULT 'income')''')
    conn.commit()
    conn.close()
    flask_app.run(host='0.0.0.0', port=PORT)
