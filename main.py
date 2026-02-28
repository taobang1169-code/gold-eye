import requests
import feedparser
import os
import re
from datetime import datetime, timedelta
from openai import OpenAI

# ---------------- 配置区 ----------------
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
KIMI_KEY = os.environ.get("KIMI_KEY")

# 监控全球核心政经源
SOURCES = {
    "路透政经": "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best",
    "WSJ商业": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
    "CNBC财经": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
    "华尔街见闻": "https://wallstreetcn.com/rss/news" # 如果RSS失效可替换为其他源
}
# ---------------------------------------

def get_global_intelligence():
    """搜罗所有核心源，提取前 3 条最重磅的新闻"""
    print("📡 正在扫描全球政经雷达...")
    intel_pool = []
    for name, url in SOURCES.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                intel_pool.append(f"【{name}】{entry.title}")
        except:
            continue
    return "\n".join(intel_pool)

def call_kimi_intelligence_center(intel_blob, market):
    """Kimi 负责将杂乱的新闻串联成“股市+黄金”的影响力地图"""
    client = OpenAI(api_key=KIMI_KEY, base_url="https://api.moonshot.cn/v1")
    
    prompt = f"""
    你现在是顶级国际智库分析师。请根据以下搜罗到的政经情报，为投资者写一份决策参考。
    
    【盘面参考】: 黄金 ¥{market['price_cny']} ({market['change_pct']}%)
    【搜罗到的原始情报】:
    {intel_blob}
    
    请按此格式输出（禁止废话）：

    🌍 全球政经核心变数：
    1. [政治/战争/政策] -> 核心逻辑及对市场的直接冲击。
    2. [经济数据/货币政策] -> 核心逻辑及对市场的直接冲击。
    
    📈 股市/黄金联动导向：
    - 股市：[看多/看空理由及避险情绪走向]
    - 黄金：[受哪些政经变数支撑或压制]
    
    决策结论：
    [一句话总结当前的盘面定调]
    """
    
    try:
        completion = client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[{"role": "system", "content": "你说话风格极其冷峻、客观，只讲逻辑，不讲废话。"},
                      {"role": "user", "content": prompt}],
            temperature=0.3
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"智库分析中断，错误详情: {str(e)}"

# ---------------- 视觉模版修复 ----------------
def send_intelligence_card(content, market):
    url = "http://www.pushplus.plus/send"
    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%H:%M')
    
    # 保持原有模版的硬核配色和结构
    bg_color = "#ffeb3b" if market['change_pct'] >= 0 else "#a5d6a7"
    formatted_content = content.replace("\n", "<br>")
    
    html = f"""
    <div style="font-family: Arial, sans-serif; background-color: #fdfdfd; padding: 15px; border-radius: 8px; border: 1px solid #e0e0e0;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 12px;">
            <div style="font-size: 18px; font-weight: 900; color: #d32f2f;">🔥 全球政经内参</div>
            <div style="font-size: 12px; color: #666; font-weight: bold;">{bj_time} 更新</div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; background: #f5f5f5; padding: 10px; border-radius: 4px; margin-bottom: 15px;">
            <div>
                <span style="font-size: 11px; color: #888;">黄金现价</span><br>
                <span style="font-size: 20px; font-weight: 900;">¥{market['price_cny']}</span>
            </div>
            <div style="background-color: {bg_color}; padding: 4px 10px; border-radius: 4px; font-weight: 800;">
                {market['change_pct']}%
            </div>
        </div>

        <div style="font-size: 14px; line-height: 1.7; color: #222;">
            {formatted_content}
        </div>

        <div style="margin-top: 15px; padding-top: 10px; border-top: 1px dashed #ccc; font-size: 11px; color: #999; text-align: center;">
            情报源：Reuters | WSJ | CNBC | Kimi Intelligence
        </div>
    </div>
    """
    
    requests.post(url, json={
        "token": PUSH_TOKEN, 
        "title": f"【政经内参】{market['price_cny']} 金价波动中", 
        "content": html, 
        "template": "html"
    })

def run_task():
    # 1. 抓金价（作为市场锚点，函数逻辑同前）
    market = get_sina_gold_price()
    if not market: return
    
    # 2. 搜罗情报
    intel_blob = get_global_intelligence()
    
    # 3. Kimi 汇总分析
    final_report = call_kimi_intelligence_center(intel_blob, market)
    
    # 4. 推送
    send_intelligence_card(final_report, market)
    print("✅ 全球政经内参已送达！")

if __name__ == "__main__":
    run_task()
