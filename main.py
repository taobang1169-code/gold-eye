import requests
import feedparser
import os
import re
import time
from datetime import datetime, timedelta

# ---------------- 配置区 ----------------
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")
# 备用：CNBC 黄金频道
RSS_URL = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"
# ---------------------------------------

def get_beijing_time():
    """获取北京时间"""
    return datetime.utcnow() + timedelta(hours=8)

def get_sina_market_data():
    """
    🔥 核弹级数据源：新浪财经底层接口
    hf_XAU = 伦敦金现货 (实时)
    fx_susdcny = 离岸人民币汇率 (实时)
    """
    print("🚀 正在接入新浪底层数据链...")
    
    headers = {
        "Referer": "https://finance.sina.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 强制重试 3 次，保证万无一失
    for i in range(3):
        try:
            # 请求接口
            url = "http://hq.sinajs.cn/list=hf_XAU,fx_susdcny"
            resp = requests.get(url, headers=headers, timeout=5)
            content = resp.text
            
            # 1. 解析伦敦金 (hf_XAU)
            # 格式: var hq_str_hf_XAU="2034.50,..."
            match_gold = re.search(r'hq_str_hf_XAU="([^"]+)"', content)
            if not match_gold: raise Exception("伦敦金数据为空")
            gold_arr = match_gold.group(1).split(',')
            price_usd = float(gold_arr[0]) # 第0位是现价
            prev_close = float(gold_arr[7]) # 第7位是昨收
            
            # 计算涨跌
            change_pct = round((price_usd - prev_close) / prev_close * 100, 2)
            
            # 2. 解析汇率 (fx_susdcny)
            match_rate = re.search(r'hq_str_fx_susdcny="([^"]+)"', content)
            if not match_rate: raise Exception("汇率数据为空")
            rate_arr = match_rate.group(1).split(',')
            rate_cny = float(rate_arr[1]) # 第1位是买入价
            
            # 3. 换算人民币价格
            price_cny = (price_usd * rate_cny) / 31.1035
            
            print(f"✅ 数据锁定: ${price_usd} | 汇率:{rate_cny}")
            return {
                "price_usd": price_usd,
                "price_cny": round(price_cny, 2),
                "rate_cny": rate_cny,
                "change_pct": change_pct
            }
            
        except Exception as e:
            print(f"⚠️ 接口波动 (第{i+1}次): {e}")
            time.sleep(1)
            
    print("❌ 最终失败：无法连接新浪接口")
    return None

def call_deepseek_strategy(news_title, market):
    print(f"⚡ 呼叫 DeepSeek 交易大脑...")
    url = "https://api.deepseek.com/chat/completions"
    
    # 如果真的极端情况没拿到数据，用文字占位，防止报错
    price_display = f"¥{market['price_cny']}" if market else "暂无报价"
    usd_display = f"${market['price_usd']}" if market else "N/A"
    
    prompt = f"""
    你现在是华尔街顶级黄金交易员，服务于中国VIP客户。
    
    【实时行情】:
    - 人民币金价: {price_display}/克
    - 伦敦金现货: {usd_display}
    - 国际涨跌幅: {market['change_pct'] if market else 0}%
    
    【突发新闻】: "{news_title}"
    
    请输出《黄金交易指令》，包含3点（严禁废话）：

    1. 🎯 **多空研判**：
       - 基于新闻和当前价格，直接给方向：【做多 Long】 / 【做空 Short】 / 【观望 Wait】。
       - 判断该新闻是否已经被价格消化（Price-in）。

    2. 🧠 **核心逻辑**：
       - 一句话解释：新闻 -> 情绪 -> 金价 的传导。
    
    3. 💰 **点位建议 (CNY)**：
       - 现价 {price_display} 附近。
       - 给出一个“抄底位”和一个“止盈位”。

    风格：像发给交易员的指令，冷酷、精准。
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
        return "AI 未返回分析"
    except:
        return "AI 连接超时"

def send_wechat(title, content, market, link):
    url = "http://www.pushplus.plus/send"
    time_str = get_beijing_time().strftime('%H:%M:%S')
    
    # 样式逻辑
    is_up = market and market['change_pct'] >= 0
    # 红涨绿跌
    color = "#d32f2f" if is_up else "#2e7d32" 
    arrow = "📈" if is_up else "📉"
    
    price_cny = market['price_cny'] if market else "---"
    price_usd = market['price_usd'] if market else "---"
    
    html = f"""
    <div style="font-family:-apple-system, sans-serif;">
        <div style="display:flex; justify-content:space-between; color:#666; font-size:12px; margin-bottom:5px;">
            <span>⚡ 黄金实盘</span>
            <span>{time_str}</span>
        </div>
        
        <div style="background:{color}; color:white; padding:15px; border-radius:8px; text-align:center; box-shadow:0 2px 8px rgba(0,0,0,0.2);">
            <div style="font-size:32px; font-weight:bold; line-height:1;">
                ¥{price_cny}
            </div>
            <div style="font-size:13px; opacity:0.9; margin-top:5px;">
                国际 ${price_usd} | {arrow} {market['change_pct'] if market else 0}%
            </div>
        </div>
        
        <div style="margin-top:15px; font-weight:600; color:#333; font-size:16px;">
            📰 {title}
        </div>
        
        <div style="margin-top:10px; padding:12px; background:#f8f9fa; border-left:4px solid {color}; border-radius:4px; color:#444; font-size:14px; line-height:1.6;">
            {content.replace(chr(10), '<br>')}
        </div>
        
        <div style="text-align:center; margin-top:15px;">
            <a href="{link}" style="color:#999; text-decoration:none; font-size:12px;">🔗 查看原始资讯</a>
        </div>
    </div>
    """
    
    title_short = f"{arrow}¥{price_cny} 策略更新"
    requests.post(url, json={"token": PUSH_TOKEN, "title": title_short, "content": html, "template": "html"})

def run_task():
    print("🔥 启动工业级数据引擎...")
    
    # 1. 死命令：必须拿到行情
    market = get_sina_market_data()
    
    if not market:
        print("💥 致命错误：所有数据源均不可用，请检查网络策略")
        return # 拿不到行情直接不发了，免得发空数据挨骂

    try:
        feed = feedparser.parse(RSS_URL)
        if len(feed.entries) > 0:
            entry = feed.entries[0]
            print(f"📰 新闻: {entry.title}")
            
            # 调试模式：True (上线后可改为关键词过滤)
            if True: 
                ai_res = call_deepseek_strategy(entry.title, market)
                send_wechat(entry.title, ai_res, market, entry.link)
                print("✅ 推送成功")
        else:
            print("📭 无新消息")
    except Exception as e:
        print(f"❌ 运行报错: {e}")

if __name__ == "__main__":
    run_task()
