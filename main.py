import requests
import feedparser
import os
import yfinance as yf
from datetime import datetime, timedelta
import time

# ---------------- 配置区 ----------------
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")
# 备用源：如果 CNBC 慢，这个源通常包含更紧凑的黄金快讯
RSS_URL = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"
# ---------------------------------------

def get_beijing_time():
    """获取北京时间"""
    return datetime.utcnow() + timedelta(hours=8)

def get_international_gold_realtime():
    """
    🔥 直连国际服务器获取 XAUUSD (伦敦金)
    不走任何国内中转，数据绝对一手。
    """
    print("🌍 正在建立国际专线 (Connecting to Yahoo Global)...")
    
    # 重试机制：如果网络抖动，自动重试 3 次
    for i in range(3):
        try:
            # 1. 获取汇率 (USD -> CNY)
            # 使用 fast_info 获取最新报价，比 history 更快
            cny_ticker = yf.Ticker("CNY=X")
            rate_cny = cny_ticker.fast_info['last_price']
            
            # 2. 获取伦敦金现货 (XAUUSD)
            gold_ticker = yf.Ticker("XAUUSD=X")
            price_usd = gold_ticker.fast_info['last_price']
            
            # 3. 获取前一日收盘价 (算涨跌幅用)
            prev_close = gold_ticker.fast_info['previous_close']
            change_pct = (price_usd - prev_close) / prev_close * 100
            
            # 4. 获取美债收益率
            bond = yf.Ticker("^TNX")
            bond_yield = bond.fast_info['last_price']

            # 换算人民币金价
            price_cny = (price_usd * rate_cny) / 31.1035
            
            print(f"✅ 获取成功 (第{i+1}次尝试)")
            return {
                "price_usd": round(price_usd, 2),
                "price_cny": round(price_cny, 2),
                "rate_cny": round(rate_cny, 4),
                "change_pct": round(change_pct, 2),
                "bond_yield": round(bond_yield, 3)
            }
            
        except Exception as e:
            print(f"⚠️ 连接波动 (尝试 {i+1}/3): {e}")
            time.sleep(2) # 等2秒重试
            
    print("❌ 国际线路暂时拥堵，无法获取实时报价")
    return None

def call_deepseek_strategy(news_title, market):
    print(f"⚡ 请求华尔街 AI 分析...")
    url = "https://api.deepseek.com/chat/completions"
    
    # 动态构建行情背景
    market_str = "行情数据同步中..."
    if market:
        market_str = f"现价 ¥{market['price_cny']}/克 (国际 ${market['price_usd']}, 涨跌 {market['change_pct']}%)"

    prompt = f"""
    你现在是高盛(Goldman Sachs)驻伦敦的黄金首席交易员。
    
    【实时行情(Real-time)】: {market_str}
    【美债收益率】: {market['bond_yield'] if market else 'N/A'}%
    【突发消息】: "{news_title}"
    
    请输出一份《伦敦金·极速交易指令》：

    1. ⏱️ **时效校验**：
       - 现在的价格(¥{market['price_cny'] if market else '?'})是否已经反映了这条新闻？
       - 如果是旧闻，直接说“已priced in，无视”。

    2. 🚦 **方向与逻辑**：
       - 必须结合【美债收益率】分析。
       - 逻辑链：新闻 -> 美债变动 -> 黄金方向。
       - 结论：【做多 Long】 / 【做空 Short】 / 【观望 Wait】。
    
    3. 💰 **点位 (CNY/克)**：
       - 基于现价 ¥{market['price_cny'] if market else '?'}。
       - 给出 3元 空间的超短线支撑/压力位。

    要求：冷酷、专业、不要废话。
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_KEY}"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if 'choices' in response.json():
            return response.json()['choices'][0]['message']['content']
        return "❌ AI 掉线"
    except:
        return "⚠️ 网络错误"

def send_wechat(title, content, market, link):
    url = "http://www.pushplus.plus/send"
    bj_time = get_beijing_time().strftime('%H:%M:%S') # 精确到秒
    
    # 颜色逻辑：红涨绿跌 (中国习惯)
    is_up = market and market['change_pct'] >= 0
    color_code = "#d32f2f" if is_up else "#2e7d32"
    arrow = "📈" if is_up else "📉"
    
    # 顶部实时报价条
    price_html = ""
    if market:
        price_html = f"""
        <div style="background:{color_code}; color:white; padding:15px; border-radius:8px; text-align:center; box-shadow:0 4px 10px rgba(0,0,0,0.2);">
            <div style="font-size:28px; font-weight:bold;">
                ¥ {market['price_cny']}
            </div>
            <div style="font-size:12px; opacity:0.9; margin-top:4px;">
                国际 ${market['price_usd']} | {arrow} {market['change_pct']}%
            </div>
        </div>
        """

    html = f"""
    <div style="font-family:sans-serif;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <b style="color:#333; font-size:16px;">⚡ 伦敦金直连</b>
            <span style="font-size:12px; color:#999;">更新: {bj_time}</span>
        </div>
        
        {price_html}
        
        <div style="margin-top:20px; font-weight:bold; color:#333; font-size:15px;">
            📰 {title}
        </div>
        
        <div style="margin-top:10px; background:#f5f5f5; padding:12px; border-left:4px solid {color_code}; border-radius:4px; font-size:14px; line-height:1.6; color:#444;">
            {content.replace(chr(10), '<br>')}
        </div>
        
        <br>
        <a href="{link}" style="display:block; text-align:center; color:#888; text-decoration:none; font-size:12px;">🔗 查看 Bloomberg 原始数据</a>
    </div>
    """
    
    # 标题必须带价格和方向
    push_title = f"{arrow} ¥{market['price_cny']} 策略送达" if market else "⚠️ 国际线路重连中"
    
    requests.post(url, json={"token": PUSH_TOKEN, "title": push_title, "content": html, "template": "html"})

def run_task():
    print("🚀 启动国际专线 (Yahoo Direct)...")
    
    # 1. 优先获取行情
    market = get_international_gold_realtime()
    
    if market:
        print(f"✅ 锁定现价: ${market['price_usd']} (¥{market['price_cny']})")
    else:
        print("❌ 警告: 国际数据源未响应")

    try:
        feed = feedparser.parse(RSS_URL)
        if len(feed.entries) > 0:
            entry = feed.entries[0]
            print(f"📰 最新: {entry.title}")
            
            # 调试模式开启
            if True: 
                ai_res = call_deepseek_strategy(entry.title, market)
                send_wechat(entry.title, ai_res, market, entry.link)
                print("✅ 策略已发出")
        else:
            print("📭 市场静默")
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    run_task()
