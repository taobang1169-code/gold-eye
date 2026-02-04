import requests
import feedparser
import os
import yfinance as yf
from datetime import datetime, timedelta

# ---------------- 配置区 ----------------
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")
RSS_URL = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"
# ---------------------------------------

def get_beijing_time():
    """获取精准北京时间"""
    return datetime.utcnow() + timedelta(hours=8)

def get_realtime_gold_cny():
    """🔥 获取【伦敦金现货 XAUUSD】并按实时汇率转为【人民币金价】"""
    print("📊 正在连接伦敦与外汇市场...")
    try:
        # XAUUSD=X: 伦敦金现货 (24小时交易，无延迟)
        # CNY=X: 美元/人民币离岸汇率
        # ^TNX: 10年期美债 (宏观参考)
        tickers = yf.Tickers("XAUUSD=X CNY=X ^TNX")
        
        # 1. 获取伦敦金现货 (美元/盎司)
        gold_data = tickers.tickers['XAUUSD=X'].history(period="1d", interval="1m")
        if gold_data.empty:
            # 如果接口偶尔抽风，尝试获取日线
            gold_data = tickers.tickers['XAUUSD=X'].history(period="1d")
            
        price_usd = gold_data['Close'].iloc[-1]
        
        # 计算日内涨跌幅 (相比开盘)
        open_price = gold_data['Open'].iloc[0] # 取今日开盘价
        change_pct = (price_usd - open_price) / open_price * 100
        
        # 2. 获取实时汇率 (1美元兑多少人民币)
        rate_data = tickers.tickers['CNY=X'].history(period="1d")
        rate_cny = rate_data['Close'].iloc[-1]
        
        # 3. 获取美债收益率
        bond_data = tickers.tickers['^TNX'].history(period="1d")
        bond_yield = bond_data['Close'].iloc[-1]
        
        # 4. 🔥 核心换算公式
        # 1金衡盎司 = 31.1034768 克
        # 人民币金价(元/克) = (国际金价$ * 汇率) / 31.1035
        price_cny_gram = (price_usd * rate_cny) / 31.1035
        
        return {
            "price_usd": round(price_usd, 2),       # 国际现货 $2035.40
            "price_cny": round(price_cny_gram, 2),  # 国内参考 ¥472.50
            "rate_cny": round(rate_cny, 4),         # 汇率 7.2345
            "change_pct": round(change_pct, 2),     # 涨跌幅 +1.2%
            "bond_yield": round(bond_yield, 3)      # 美债 4.02%
        }
    except Exception as e:
        print(f"⚠️ 行情接口异常: {e}")
        return None

def call_deepseek_strategy(news_title, market):
    print(f"⚡ 请求 AI 进行【伦敦金->人民币金】穿透分析...")
    url = "https://api.deepseek.com/chat/completions"
    
    # 动态构建提示词
    price_info = "行情获取失败"
    if market:
        price_info = f"现价 ¥{market['price_cny']}/克 (国际 ${market['price_usd']}, 汇率 {market['rate_cny']})"

    prompt = f"""
    你现在是服务中国用户的黄金交易专家。
    
    【当前实时行情 (北京时间)】:
    {price_info}
    10年美债: {market['bond_yield'] if market else 'N/A'}%
    
    【突发新闻】: "{news_title}"
    
    请输出一份《人民币黄金操作内参》，字数200字以内，必须包含：

    1. ⏱️ **时效性判定**：
       - 这条新闻是“刚才”发生的，还是“旧闻”？对现在的价格(¥{market['price_cny'] if market else '?'})还有效吗？

    2. ⚖️ **价格传导逻辑**：
       - 分析【国际金价】和【人民币汇率】的对冲关系。
       - 例如：虽然美元金跌了，但人民币贬值，国内金价是否能抗跌？
    
    3. 🎯 **实战建议 (元/克)**：
       - 针对 **人民币金价 (¥{market['price_cny'] if market else '?'})**。
       - 给出：【追多】/【抄底】/【止盈】/【观望】。
       - 预估下方支撑位（例如：回踩 470元/克 接货）。

    风格：干练、直接，像发给VIP客户的短信。
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个只看真实数据、痛恨滞后信息的实战派交易员。"},
            {"role": "user", "content": prompt}
        ],
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
        return "❌ AI 正在等待数据..."
    except Exception:
        return "⚠️ 网络超时"

def send_wechat(title, content, market, link):
    url = "http://www.pushplus.plus/send"
    bj_time = get_beijing_time().strftime('%H:%M')
    
    # 智能配色：根据涨跌变色 (红涨绿跌)
    is_up = market and market['change_pct'] >= 0
    bg_color = "#fff3e0" if is_up else "#e8f5e9"  # 涨用橙红底，跌用浅绿底
    text_color = "#d84315" if is_up else "#2e7d32"
    arrow = "📈" if is_up else "📉"
    
    # 顶部醒目行情条
    ticker_html = ""
    if market:
        ticker_html = f"""
        <div style="background:{bg_color}; padding:15px; border-radius:8px; text-align:center; border:1px solid {text_color};">
            <div style="font-size:24px; font-weight:900; color:{text_color};">
                ¥ {market['price_cny']} <span style="font-size:14px;">元/克</span>
            </div>
            <div style="font-size:12px; color:#666; margin-top:5px;">
                国际 ${market['price_usd']} {arrow} {market['change_pct']}% | 汇率 {market['rate_cny']}
            </div>
        </div>
        """

    html = f"""
    <div style="font-family:'Helvetica Neue', Helvetica, sans-serif;">
        <h3 style="color:#333; margin-bottom:5px;">⚡ 伦敦金实时内参</h3>
        <p style="font-size:12px; color:#999;">北京时间 {bj_time} | 实时无延迟</p>
        
        {ticker_html}
        
        <div style="margin-top:20px; font-weight:bold; font-size:15px; color:#333;">
            🔔 {title}
        </div>
        
        <div style="margin-top:10px; padding:10px; background:#f9f9f9; border-left:4px solid {text_color}; line-height:1.6; font-size:14px; color:#444;">
            {content.replace(chr(10), '<br>')}
        </div>
        
        <br>
        <a href="{link}" style="display:block; width:100%; text-align:center; padding:10px 0; background:{text_color}; color:white; text-decoration:none; border-radius:4px;">📊 查看分钟级K线</a>
    </div>
    """
    
    # 标题直接带价格，不点开也能看
    push_title = f"¥{market['price_cny']} {arrow} 策略发出" if market else "⚠️ 行情获取失败"
    
    data = {"token": PUSH_TOKEN, "title": push_title, "content": html, "template": "html"}
    requests.post(url, json=data)

def run_task():
    print("🚀 启动伦敦金零延迟引擎...")
    
    # 1. 优先抓取行情，如果拿不到行情，后面分析也没意义
    market = get_realtime_gold_cny()
    if market:
        print(f"✅ 伦敦金锁定: ${market['price_usd']} -> 折算 ¥{market['price_cny']}/克")
    else:
        print("❌ 无法连接国际市场，请检查网络")

    try:
        feed = feedparser.parse(RSS_URL)
        if len(feed.entries) > 0:
            entry = feed.entries[0]
            print(f"📰 捕获信号: {entry.title}")
            
            # 调试模式常开，确保你此刻能收到
            if True: 
                ai_res = call_deepseek_strategy(entry.title, market)
                send_wechat(entry.title, ai_res, market, entry.link)
                print("✅ 实时策略已送达")
        else:
            print("📭 市场暂无波动")
    except Exception as e:
        print(f"❌ 系统错误: {e}")

if __name__ == "__main__":
    run_task()
