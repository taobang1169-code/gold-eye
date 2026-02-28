import requests
import feedparser
import os
import re
from datetime import datetime, timedelta
from openai import OpenAI

# ---------------- 配置区 ----------------
# 请确保 GitHub Secrets 中配置了以下三个变量
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
KIMI_KEY = os.environ.get("KIMI_KEY")

RSS_SOURCES = {
    "路透地缘政治": "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best",
    "WSJ商业政策": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
    "CNBC实时财经": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"
}
# ---------------------------------------

def get_beijing_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime('%H:%M')

def get_sina_gold_price():
    headers = {"Referer": "https://finance.sina.com.cn/"}
    try:
        url = "http://hq.sinajs.cn/list=hf_XAU,fx_susdcny"
        resp = requests.get(url, headers=headers, timeout=10)
        content = resp.text
        match_gold = re.search(r'hq_str_hf_XAU="([^"]+)"', content)
        if not match_gold: return None
        gold_arr = match_gold.group(1).split(',')
        price_usd, prev_close = float(gold_arr[0]), float(gold_arr[7])
        match_rate = re.search(r'hq_str_fx_susdcny="([^"]+)"', content)
        rate_cny = float(match_rate.group(1).split(',')[1]) if match_rate else 7.28
        price_cny = (price_usd * rate_cny) / 31.1035
        change_pct = (price_usd - prev_close) / prev_close * 100
        return {"price_cny"^_^: round(price_cny, 2), "change_pct": round(change_pct, 2)}
    except:
        return {"price_cny": "数据延迟", "change_pct": 0.0}

def fetch_global_news():
    news_items = []
    for tag, url in RSS_SOURCES.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                news_items.append(f"【{tag}】{entry.title}")
        except:
            continue
    return "\n".join(news_items) if news_items else "未能获取到最新资讯"

def call_kimi_intelligence(intel_blob, market):
    client = OpenAI(api_key=KIMI_KEY, base_url="https://api.moonshot.cn/v1")
    prompt = f"""
    你现在是顶级智库分析师。请分析以下情报对股市和黄金的影响。
    【黄金锚点】: ¥{market['price_cny']} ({market['change_pct']}%)
    【情报池】:
    {intel_blob}
    
    格式要求：
    🌍 政经变数汇总：
    1. [重点1]
    2. [重点2]
    
    📈 联动导向：
    - 股市：[分析]
    - 黄金：[分析]
    
    简评：[一句话定调]
    """
    try:
        completion = client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"AI 分析异常: {str(e)}"

def send_pushplus(content, market):
    """
    🚀 修复版推送函数
    """
    url = "http://www.pushplus.plus/send"
    bj_time = get_beijing_time()
    bg_color = "#ffeb3b" if market['change_pct'] >= 0 else "#a5d6a7"
    
    # 转换为 HTML 换行
    html_content = content.replace("\n", "<br>")
    
    body = f"""
    <div style="font-family: sans-serif; padding: 15px; border: 1px solid #eee; border-radius: 10px; background: #fafafa;">
        <div style="border-bottom: 2px solid #333; padding-bottom: 5px; margin-bottom: 10px; display: flex; justify-content: space-between;">
            <b>🌍 全球政经雷达</b> <span>{bj_time}</span>
        </div>
        <div style="margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 24px; font-weight: bold;">¥{market['price_cny']}</span>
            <span style="background:{bg_color}; padding: 3px 8px; border-radius: 4px;">{market['change_pct']}%</span>
        </div>
        <div style="font-size: 14px; line-height: 1.6; color: #444;">
            {html_content}
        </div>
    </div>
    """
    
    payload = {
        "token": PUSH_TOKEN,
        "title": f"全球内参 | 黄金 ¥{market['price_cny']}",
        "content": body,
        "template": "html"
    }
    
    try:
        r = requests.post(url, json=payload, timeout=20)
        print(f"推送状态码: {r.status_code}, 返回信息: {r.text}")
    except Exception as e:
        print(f"推送请求失败: {e}")

def run_task():
    market = get_sina_gold_price()
    intel_blob = fetch_global_news()
    ai_report = call_kimi_intelligence(intel_blob, market)
    send_pushplus(ai_report, market)

if __name__ == "__main__":
    run_task()
