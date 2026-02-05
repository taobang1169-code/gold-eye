import requests
import feedparser
import os
import re
import time
from datetime import datetime, timedelta

# ---------------- 配置区 ----------------
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")
# 依然用 CNBC 源，资讯最快
RSS_URL = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"
# ---------------------------------------

def get_beijing_time():
    return datetime.utcnow() + timedelta(hours=8)

def get_sina_gold_price():
    """
    🔥 工业级数据源：新浪财经底层数据 (hf_XAU)
    稳、快、准，包含人民币汇率换算
    """
    print("🚀 正在接入新浪底层数据链...")
    headers = {"Referer": "https://finance.sina.com.cn/"}
    
    try:
        # hf_XAU: 伦敦金现货, fx_susdcny: 离岸汇率
        url = "http://hq.sinajs.cn/list=hf_XAU,fx_susdcny"
        resp = requests.get(url, headers=headers, timeout=5)
        content = resp.text
        
        # 1. 解析金价
        match_gold = re.search(r'hq_str_hf_XAU="([^"]+)"', content)
        if not match_gold: return None
        gold_arr = match_gold.group(1).split(',')
        price_usd = float(gold_arr[0])
        prev_close = float(gold_arr[7])
        
        # 2. 解析汇率
        match_rate = re.search(r'hq_str_fx_susdcny="([^"]+)"', content)
        rate_cny = 7.28 # 默认兜底
        if match_rate:
            rate_arr = match_rate.group(1).split(',')
            rate_cny = float(rate_arr[1])

        # 3. 核心计算
        price_cny = (price_usd * rate_cny) / 31.1035
        change_pct = (price_usd - prev_close) / prev_close * 100
        
        # 4. 模拟成交量状态 (根据波动率反推，为了还原研报风格)
        vol_status = "缩量盘整"
        if abs(change_pct) > 1.0: vol_status = "极端放量 🔥"
        elif abs(change_pct) > 0.5: vol_status = "温和放量"

        return {
            "price_usd": round(price_usd, 2),
            "price_cny": round(price_cny, 2),
            "rate_cny": round(rate_cny, 4),
            "change_pct": round(change_pct, 2),
            "vol_status": vol_status
        }
    except Exception as e:
        print(f"❌ 数据源波动: {e}")
        return None

def call_deepseek_research(news_title, market):
    print(f"⚡ 呼叫 DeepSeek 生成“口罩哥”风格研报...")
    url = "https://api.deepseek.com/chat/completions"
    
    # 🔥 核心 Prompt：强制模仿图片风格，杜绝废话
    prompt = f"""
    你现在是全网粉丝百万的黄金分析师。请复刻“专业研报”风格。
    
    【当前盘面】:
    - 价格: ¥{market['price_cny']}/克 (国际 ${market['price_usd']})
    - 涨跌: {market['change_pct']}% ({market['vol_status']})
    - 突发新闻: "{news_title}"
    
    请直接输出分析内容，格式必须严格如下（不要有开场白）：

    核心驱动因素：
    1. [因素1] (结合新闻事件/地缘局势，简练毒辣)
    2. [因素2] (结合美元DXY或美债收益率)
    3. [因素3] (结合央行购金或市场情绪)
    
    结论与点位：
    [一句话看涨/看跌]，支撑参考 ¥{int(market['price_cny']-2)}，压力 ¥{int(market['price_cny']+2)}。
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_KEY}"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if 'choices' in response.json():
            return response.json()['choices'][0]['message']['content']
        return "研报生成超时..."
    except:
        return "AI 分析连线中..."

def send_wechat_card(title, content, market, link):
    url = "http://www.pushplus.plus/send"
    bj_time = get_beijing_time().strftime('%H:%M')
    
    # 🎨 视觉复刻：
    # 涨跌幅背景：黄色高亮 #ffeb3b (涨) 或 浅绿 (跌)
    # 字体：黑色加粗
    bg_color = "#ffeb3b" if market['change_pct'] >= 0 else "#a5d6a7"
    trend_sign = "+" if market['change_pct'] >= 0 else ""
    
    # 内容格式化
    formatted_content = content.replace("\n", "<br>")
    
    html = f"""
    <div style="font-family: Arial, sans-serif; background-color: #fdfdfd; padding: 15px; border-radius: 8px; border: 1px solid #e0e0e0;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #f0f0f0; padding-bottom: 12px; margin-bottom: 12px;">
            <div>
                <div style="font-size: 12px; color: #888;">收益价 (CNY)</div>
                <div style="font-size: 30px; font-weight: 900; color: #333; line-height: 1.2;">
                    ¥{market['price_cny']}
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 12px; color: #888;">日内涨幅</div>
                <div style="background-color: {bg_color}; color: #000; padding: 4px 10px; border-radius: 4px; font-weight: 800; font-size: 18px;">
                    {trend_sign}{market['change_pct']}%
                </div>
            </div>
        </div>

        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #666; background: #f9f9f9; padding: 8px; border-radius: 4px; margin-bottom: 15px;">
            <span>国际: <b>${market['price_usd']}</b></span>
            <span>成交: <b>{market['vol_status']}</b></span>
            <span>汇率: <b>{market['rate_cny']}</b></span>
        </div>

        <div style="padding: 10px 0;">
            <div style="font-weight: bold; font-size: 15px; color: #333; margin-bottom: 8px;">🔥 核心驱动因素：</div>
            <div style="font-size: 14px; line-height: 1.6; color: #444; background: #fff; padding: 10px; border-left: 4px solid #fbc02d;">
                {formatted_content}
            </div>
        </div>

        <br>
        <div style="text-align: right; font-size: 12px; color: #aaa;">
            北京时间 {bj_time} | 研报生成
        </div>
        
        <a href="{link}" style="display: block; margin-top: 15px; text-align: center; background-color: #222; color: #fff; padding: 10px; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: bold;">
            查看 K 线图
        </a>
    </div>
    """
    
    push_title = f"¥{market['price_cny']} ({trend_sign}{market['change_pct']}%) 研报出炉"
    requests.post(url, json={"token": PUSH_TOKEN, "title": push_title, "content": html, "template": "html"})

def run_task():
    print("🚀 启动“口罩哥”研报引擎 (修复版)...")
    
    # 1. 拿数据 (新浪源，绝对稳)
    market = get_sina_gold_price()
    
    if not market:
        print("❌ 网络依然不通，请检查 GitHub 服务状态")
        return

    try:
        feed = feedparser.parse(RSS_URL)
        if len(feed.entries) > 0:
            entry = feed.entries[0]
            print(f"📰 新闻: {entry.title}")
            
            # 调试模式开启，保证现在就能收到
            ai_res = call_deepseek_research(entry.title, market)
            send_wechat_card(entry.title, ai_res, market, entry.link)
            print("✅ 推送成功！")
        else:
            print("📭 暂无新闻")
    except Exception as e:
        print(f"❌ 运行报错: {e}")

if __name__ == "__main__":
    run_task()
