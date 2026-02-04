import requests
import feedparser
import os
import re
from datetime import datetime
# -----------------------------------------------
# 配置区
# -----------------------------------------------
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")

# 🔥 核心升级：更换为 Investing.com 黄金/金属 实时RSS源
# 这个源比CNBC更聚焦，更新速度更快
RSS_URL = "https://www.investing.com/rss/commodities_metals.rss"

def call_deepseek_strategy(news_title, news_link):
    print(f"⚡ 正在请求机构分析: {news_title}")
    url = "https://api.deepseek.com/chat/completions"
    
    # 🧠 华尔街交易员指令：强制要求输出时间节点和结论
    prompt = f"""
    你现在是高盛(Goldman Sachs)首席黄金交易员。请分析这条突发新闻："{news_title}"
    链接：{news_link}

    请忽略客套话，直接输出一份【交易策略单】，必须严格包含以下4点：

    1. 🎯 **多空结论**：(仅限：大幅利多 / 小幅利多 / 震荡 / 小幅利空 / 大幅利空)，并给出置信度(0-100%)。
    2. ⏱️ **变盘节点**：新闻中是否隐含具体时间？(如：今晚20:30 CPI、周四凌晨会议)。如果没有，请注明“即刻生效”或“情绪发酵期”。
    3. ⛓️ **逻辑推演**：用箭头表示因果（如：非农超预期 -> 加息概率升 -> 美元涨 -> 黄金跌）。
    4. 💰 **操作建议**：激进者/稳健者分别怎么做？（如：现价做多、回踩1980接多、观望）。

    格式要求：使用Emoji，条理分明，字数200字以内，重点加粗。
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个冷酷、精准的机构交易员，只说干货，不说废话。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4 # 降低随机性，提高精准度
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
            return "❌ 机构通道拥堵（AI未返回）"
    except Exception as e:
        print(f"API报错: {e}")
        return "⚠️ 数据连接中断"

def send_wechat(title, content, link):
    url = "http://www.pushplus.plus/send"
    
    # 🎨 微信消息美化：模仿彭博终端风格
    html = f"""
    <div style="border-left: 5px solid #d4af37; padding-left: 12px; margin-bottom: 15px;">
        <h3 style="color: #333; margin:0;">🏦 华尔街情报 (Investing.com)</h3>
        <p style="color: #888; font-size: 12px; margin-top:5px;">{datetime.now().strftime('%m-%d %H:%M')}</p>
    </div>
    
    <div style="background-color: #f7f7f7; padding: 15px; border-radius: 8px; color: #333; font-size: 15px; line-height: 1.6;">
        {content.replace(chr(10), '<br>')}
    </div>
    
    <div style="margin-top: 20px; text-align: center;">
        <a href='{link}' style="display: inline-block; background: #d4af37; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">👉 查看原始图表</a>
    </div>
    """
    
    data = {
        "token": PUSH_TOKEN, 
        "title": f"🚨 {title[:10]}... (AI分析)", 
        "content": html, 
        "template": "html"
    }
    requests.post(url, json=data)

def run_task():
    print("🌍 正在接入 Investing.com 专线...")
    
    try:
        # 增加 headers 伪装成浏览器，防止被拦截
        feed = feedparser.parse(RSS_URL)
        
        if len(feed.entries) > 0:
            # 只取最新的一条
            entry = feed.entries[0]
            print(f"捕获信号: {entry.title}")
            
            # --- 关键词过滤系统 ---
            # 只有标题包含这些词才推送（你可以自己加减）
            keywords = ["Gold", "Silver", "Fed", "Dollar", "Rate", "CPI", "PPI", "Trump", "China", "XAU"]
            
            # 为了让你立刻看到新版效果，第一次运行我们暂时不限制关键词
            # 如果想正式启用过滤，把 if True 改为 if any(...)
            if True: 
            # if any(k.lower() in entry.title.lower() for k in keywords):
                print(">>> 触发高盛模型分析...")
                ai_res = call_deepseek_strategy(entry.title, entry.link)
                send_wechat(entry.title, ai_res, entry.link)
                print("✅ 策略已送达")
            else:
                print("🚫 只有普通新闻，跳过推送")
        else:
            print("📭 市场暂无更新")
            
    except Exception as e:
        print(f"❌ 系统故障: {e}")

if __name__ == "__main__":
    run_task()
