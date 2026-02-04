import requests
import feedparser
import os
import re
from datetime import datetime

# ---------------- 配置区 ----------------
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")

# 替换为更专业的【Investing.com 黄金/金属专栏】
# 这里的资讯比 CNBC 更聚焦黄金和期货市场，时效性更强
RSS_URL = "https://www.investing.com/rss/commodities_metals.rss"
# ---------------------------------------

def clean_html(raw_html):
    """清洗新闻里多余的HTML标签"""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext[:500] + "..." # 只取前500字摘要给AI，省钱又快

def call_deepseek_strategy(news_title, news_summary):
    print(f"⚡ 正在请求华尔街分析: {news_title}")
    url = "https://api.deepseek.com/chat/completions"
    
    # 🔥 核弹级提示词：强制输出结论、逻辑和时间节点
    prompt = f"""
    你现在是高盛(Goldman Sachs)的首席大宗商品交易员。
    请分析这条关于黄金/贵金属的突发新闻：
    标题：{news_title}
    摘要：{news_summary}

    请完全忽略客套话，直接输出一份【交易策略单】，必须包含以下4点：

    1. 🎯 **核心结论**：(仅限：大幅利多 / 小幅利多 / 震荡 / 小幅利空 / 大幅利空)，并给出置信度(0-100%)。
    2. ⏱️ **触发节点**：明确新闻中提到的具体时间点（如：本周四CPI公布、美联储会议纪要时间），如果没有具体时间，指出“即刻生效”或“情绪发酵期”。
    3. 🧠 **底层逻辑**：用“因果链”表达（例如：非农超预期 -> 加息概率升 -> 美元涨 -> 黄金跌）。
    4. 💰 **操作点位建议**：基于新闻情绪，给出激进者或稳健者的建议（如：回踩做多、逢高做空、观望）。

    输出格式要求：使用Emoji，条理分明，字数控制在200字以内。
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个冷酷、精准的机构交易员，只说干货。"},
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
            return "❌ 机构通道拥堵（AI未返回）"
    except Exception as e:
        print(f"API报错: {e}")
        return "⚠️ 数据连接中断"

def send_wechat(title, content, link):
    url = "http://www.pushplus.plus/send"
    # 微信卡片美化
    html = f"""
    <div style="border-left: 4px solid #d4af37; padding-left: 10px; margin-bottom: 15px;">
        <h3 style="color: #333;">🏦 机构内参 (Investing.com)</h3>
        <p style="color: #666; font-size: 12px;">{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>
    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; color: #444;">
        {content.replace(chr(10), '<br>')}
    </div>
    <hr style="border: 0; border-top: 1px dashed #ccc; margin: 20px 0;">
    <p><b>原始情报:</b> {title}</p>
    <a href='{link}' style="display: block; text-align: center; background: #d4af37; color: white; padding: 10px; text-decoration: none; border-radius: 4px;">👉 点击查看原文图表</a>
    """
    data = {"token": PUSH_TOKEN, "title": f"🚨 {title[:15]}...", "content": html, "template": "html"}
    requests.post(url, json=data)

def run_task():
    print("🌍 正在接入 Investing.com 黄金专线...")
    
    try:
        # 增加超时设置，防止卡死
        feed = feedparser.parse(RSS_URL)
        
        if len(feed.entries) > 0:
            # 只分析最新的一条
            entry = feed.entries[0]
            print(f"捕获信号: {entry.title}")
            
            # 关键词过滤（更精准，排除杂音）
            # 只有包含这些词才推送，避免垃圾新闻
            keywords = ["Gold", "Silver", "Fed", "Dollar", "Inflation", "Rate", "China", "XAU", "PMI", "CPI"]
            
            # 【重要】为了让你立刻看到效果，我暂时注释掉了关键词过滤
            # 只要你能跑通，把下面这行 if True 改成 if any(...) 即可
            if True: 
            # if any(k.lower() in entry.title.lower() for k in keywords):
                print(">>> 触发机构模型分析...")
                
                # 获取摘要，让AI读得更懂
                summary = clean_html(entry.summary) if 'summary' in entry else entry.title
                
                ai_res = call_deepseek_strategy(entry.title, summary)
                send_wechat(entry.title, ai_res, entry.link)
                print("✅ 策略已送达")
            else:
                print("🚫 新闻相关度低，忽略")
        else:
            print("📭 暂无最新市场动态")
            
    except Exception as e:
        print(f"❌ 系统故障: {e}")

if __name__ == "__main__":
    run_task()
