import requests
import feedparser
import os
import re
from datetime import datetime

# ---------------- 配置区 ----------------
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")

# ⚡️ 核心升级：换回最稳定的华尔街源，但锁定【大宗商品与期货】频道
# 这个源包含 黄金、原油、美债、美元 的实时变动，且不会屏蔽机器人
RSS_URL = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"
# ---------------------------------------

def call_deepseek_strategy(news_title, news_link):
    print(f"⚡ 正在请求华尔街分析: {news_title}")
    url = "https://api.deepseek.com/chat/completions"
    
    # 🔥 机构级提示词：要求输出【时间表】和【点位】
    prompt = f"""
    你现在是华尔街顶级对冲基金的宏观交易主管。
    请分析这条最新的大宗商品/宏观新闻："{news_title}"
    (原文链接: {news_link})

    我需要一份可执行的【作战指令】，必须严格包含以下内容：

    1. 🚦 **交易信号**：
       - 方向：(做多 XAUUSD / 做空 XAUUSD / 观望)
       - 强度：(⭐⭐⭐ / ⭐⭐ / ⭐)
    
    2. ⏰ **变盘时间表**：
       - 根据新闻内容，指出具体的行情引爆点（例如：“今晚20:30 CPI公布时”、“美联储会议纪要发布后”）。
       - 如果是突发消息，标注为“即刻生效”。

    3. 🧠 **核心逻辑链**：
       - 用箭头表示传导（如：非农爆冷 ➔ 美元跳水 ➔ 黄金拉升）。
       
    4. 🛡️ **风控建议**：
       - 给出关键支撑位或压力位的预判（如果新闻里没提，请根据宏观经验推演）。

    **要求：** 拒绝废话，像发给交易员的指令一样简练、凶狠。字数200字以内。
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个只看数据和利润的冷血交易员。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_KEY}"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        result = response.json()
        if 'choices' in result:
            return result['choices'][0]['message']['content']
        else:
            return "❌ AI 思考超时"
    except Exception as e:
        print(f"API报错: {e}")
        return "⚠️ AI 接口异常"

def send_wechat(title, content, link):
    url = "http://www.pushplus.plus/send"
    current_time = datetime.now().strftime('%H:%M')
    
    # 微信卡片设计：红绿灯风格
    color = "#d9534f" if "做空" in content else "#5cb85c" if "做多" in content else "#f0ad4e"
    
    html = f"""
    <div style="border-top: 5px solid {color}; padding: 15px; background: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <h3 style="margin-top:0; color: #333;">⚡ 华尔街快讯 ({current_time})</h3>
        <p style="font-size:14px; color:#666; margin-bottom:15px;">{title}</p>
        <div style="background: #f8f9fa; padding: 10px; border-radius: 4px; font-size: 15px; line-height: 1.6;">
            {content.replace(chr(10), '<br>')}
        </div>
        <br>
        <a href='{link}' style="display:block; text-align:center; background:{color}; color:#fff; padding:8px; text-decoration:none; border-radius:4px;">📊 查看原始图表</a>
    </div>
    """
    data = {"token": PUSH_TOKEN, "title": f"🚨 黄金情报 {current_time}", "content": html, "template": "html"}
    requests.post(url, json=data)

def run_task():
    print("🌍 正在接入 CNBC 大宗商品专线...")
    
    try:
        feed = feedparser.parse(RSS_URL)
        if len(feed.entries) > 0:
            entry = feed.entries[0]
            print(f"捕获头条: {entry.title}")
            
            # --- 关键词滤网（只抓跟钱有关的）---
            # 如果新闻标题里没有这些词，直接扔掉，宁缺毋滥
            target_keywords = ["Gold", "Silver", "Fed", "Dollar", "Rate", "Inflation", "Oil", "Treasury", "Stocks", "China"]
            
            # 为了让你立刻收到测试消息，我加了 'or True'，
            # ⚠️ 测试成功后，你可以把 'or True' 删掉，只保留关键词过滤
            if any(k in entry.title for k in target_keywords) or True:
                print(">>> 触发分析引擎...")
                ai_res = call_deepseek_strategy(entry.title, entry.link)
                send_wechat(entry.title, ai_res, entry.link)
                print("✅ 交易指令已发送")
            else:
                print("😴 无关新闻，跳过")
        else:
            print("📭 市场平静，无新消息")
            
    except Exception as e:
        print(f"❌ 程序异常: {e}")

if __name__ == "__main__":
    run_task()
