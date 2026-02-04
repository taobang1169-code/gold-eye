import requests
import feedparser
import os
import yfinance as yf
from datetime import datetime

# ---------------- 配置区 ----------------
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")
RSS_URL = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"
# ---------------------------------------

def get_market_data():
    """🔥 获取实时宏观数据：黄金、美债、美元"""
    print("📊 正在连接全球交易所获取实时报价...")
    try:
        # GC=F: 黄金期货, ^TNX: 10年美债, DX-Y.NYB: 美元指数
        tickers = yf.Tickers("GC=F ^TNX DX-Y.NYB")
        
        # 黄金数据
        gold = tickers.tickers['GC=F'].history(period="1d")
        gold_price = gold['Close'].iloc[-1]
        gold_change = (gold_price - gold['Open'].iloc[-1]) / gold['Open'].iloc[-1] * 100
        
        # 美债数据
        bond = tickers.tickers['^TNX'].history(period="1d")
        bond_yield = bond['Close'].iloc[-1]
        
        # 美元数据
        dxy = tickers.tickers['DX-Y.NYB'].history(period="1d")
        dxy_price = dxy['Close'].iloc[-1]
        
        return {
            "gold_price": round(gold_price, 2),
            "gold_change": round(gold_change, 2),
            "bond_yield": round(bond_yield, 3),
            "dxy_price": round(dxy_price, 2)
        }
    except Exception as e:
        print(f"⚠️ 无法获取行情数据: {e}")
        return None

def call_deepseek_macro(news_title, market_data):
    print(f"⚡ 正在进行【新闻+盘面】深度耦合分析...")
    url = "https://api.deepseek.com/chat/completions"
    
    # 构建实时数据背景板
    market_context = ""
    if market_data:
        market_context = f"""
        【当前盘面实况】：
        1. 黄金(Gold): ${market_data['gold_price']} (日内涨跌: {market_data['gold_change']}%)
        2. 10年期美债收益率(US10Y): {market_data['bond_yield']}% (黄金定价之锚)
        3. 美元指数(DXY): {market_data['dxy_price']}
        """

    # 🔥 机构策略师提示词
    prompt = f"""
    你现在是桥水基金(Bridgewater)的首席宏观策略师。
    
    【突发新闻】："{news_title}"
    {market_context}
    
    请结合【当前盘面实况】和【突发新闻】，进行深度归因分析。
    你的任务是寻找“预期差”和“逻辑背离”。

    请输出一份《伦敦金(XAU/USD)深度复盘》：

    1. 🕵️‍♂️ **盘面异动侦测**：
       - 不要只看新闻！看一眼美债收益率和美元。
       - 现在的金价波动，是美债驱动的吗？还是避险情绪驱动的？（结合数据回答）
       
    2. 🧠 **深度逻辑拆解** (重点)：
       - 建立核心逻辑链：事件 -> 实际利率/通胀预期 -> 资金流向 -> 黄金。
       - 例如："虽然新闻利空，但美债收益率大跌，说明市场在交易衰退预期，这对黄金其实是大利多。"

    3. 🎯 **结论与关键点位**：
       - 结论：【强力买入】/【逢高做空】/【右侧观望】。
       - 变盘节点：具体的时间点或事件。
       - 支撑/压力位：基于当前 ${market_data['gold_price'] if market_data else '市价'} 给出上下15美元的关键位置。

    风格要求：极度专业，数据导向，逻辑犀利，像华尔街内参一样。字数200字。
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一位依据数据说话的宏观经济学家，拒绝模棱两可。"},
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
            return "❌ 策略分析超时"
    except Exception as e:
        print(f"API报错: {e}")
        return "⚠️ AI接口异常"

def send_wechat(title, content, market_data):
    url = "http://www.pushplus.plus/send"
    current_time = datetime.now().strftime('%m-%d %H:%M')
    
    # 顶部数据栏
    data_banner = ""
    if market_data:
        color_gold = "red" if market_data['gold_change'] > 0 else "green"
        data_banner = f"""
        <div style="background:#f4f4f4; padding:8px; font-size:12px; border-radius:4px; margin-bottom:10px; color:#555;">
            💰 黄金: <b style="color:{color_gold}">${market_data['gold_price']} ({market_data['gold_change']}%)</b> | 
            📉 美债: <b>{market_data['bond_yield']}%</b> | 
            💵 DXY: <b>{market_data['dxy_price']}</b>
        </div>
        """

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <div style="border-left: 4px solid #b8860b; padding-left: 12px;">
            <h3 style="margin:0; color:#333;">🏦 华尔街机构内参</h3>
            <p style="margin:4px 0 0 0; font-size:12px; color:#888;">{current_time} · 深度宏观版</p>
        </div>
        <hr style="border:0; border-top:1px solid #eee; margin:15px 0;">
        
        {data_banner}
        
        <h4 style="margin:10px 0; color:#000;">📰 {title}</h4>
        
        <div style="background:#fffaf0; padding:15px; border-radius:6px; color:#444; font-size:15px; line-height:1.7;">
            {content.replace(chr(10), '<br>')}
        </div>
    </div>
    """
    
    # 标题里直接带上涨跌幅，一眼看到重点
    title_prefix = f"🔥 黄金{'📈' if market_data and market_data['gold_change']>0 else '📉'}" 
    data = {"token": PUSH_TOKEN, "title": f"{title_prefix} 深度内参 {current_time}", "content": html, "template": "html"}
    requests.post(url, json=data)

def run_task():
    print("🚀 启动高盛级分析引擎...")
    
    # 1. 先获取真实行情数据
    market_data = get_market_data()
    if market_data:
        print(f"✅ 行情获取成功: 黄金 ${market_data['gold_price']}")
    else:
        print("⚠️ 行情获取失败，将进行纯逻辑分析")

    try:
        feed = feedparser.parse(RSS_URL)
        if len(feed.entries) > 0:
            entry = feed.entries[0]
            print(f"锁定新闻: {entry.title}")
            
            # 关键词过滤
            keywords = ["Gold", "Fed", "CPI", "PPI", "Job", "Yield", "Rate", "Powell"]
            # 调试模式常开，确保你能收到反馈
            if True: 
                ai_res = call_deepseek_macro(entry.title, market_data)
                send_wechat(entry.title, ai_res, market_data)
                print("✅ 深度研报已推送")
        else:
            print("📭 市场静默")
            
    except Exception as e:
        print(f"❌ 系统崩溃: {e}")

if __name__ == "__main__":
    run_task()
