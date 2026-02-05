import requests
import feedparser
import os
import re
import json
import time
from datetime import datetime, timedelta

# ---------------- 配置区 ----------------
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")
RSS_URL = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"
HISTORY_FILE = "trade_history.json" # 账本文件
# ---------------------------------------

def get_beijing_time():
    return datetime.utcnow() + timedelta(hours=8)

def get_sina_market():
    """获取新浪实时行情"""
    headers = {"Referer": "https://finance.sina.com.cn/"}
    try:
        url = "http://hq.sinajs.cn/list=hf_XAU,fx_susdcny"
        resp = requests.get(url, headers=headers, timeout=5)
        content = resp.text
        
        match_gold = re.search(r'hq_str_hf_XAU="([^"]+)"', content)
        if not match_gold: return None
        gold_arr = match_gold.group(1).split(',')
        price_usd = float(gold_arr[0])
        
        match_rate = re.search(r'hq_str_fx_susdcny="([^"]+)"', content)
        rate_cny = 7.28
        if match_rate:
            rate_cny = float(match_rate.group(1).split(',')[1])

        price_cny = (price_usd * rate_cny) / 31.1035
        return {"price_usd": price_usd, "price_cny": round(price_cny, 2)}
    except:
        return None

def manage_ledger(current_market):
    """
    📖 会计系统：核算上次胜负，记录本次初始状态
    """
    # 1. 读取旧账本
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            try:
                history = json.load(f)
            except:
                pass

    # 2. 核算上一笔交易 (Settlement)
    last_win = False
    if history:
        last_trade = history[-1]
        # 如果上一笔还是"Pending"状态，现在进行结算
        if last_trade.get("status") == "Pending":
            entry_price = last_trade["entry_price"]
            direction = last_trade["direction"]
            curr_price = current_market["price_cny"]
            
            # 简单粗暴的胜负判定：方向对就是赢
            # (实际交易要看盈亏比，这里为了统计方便先看方向)
            if direction == "做多" and curr_price > entry_price:
                last_trade["status"] = "Win"
                last_trade["pnl"] = f"+{round(curr_price - entry_price, 2)}"
                last_win = True
            elif direction == "做空" and curr_price < entry_price:
                last_trade["status"] = "Win"
                last_trade["pnl"] = f"+{round(entry_price - curr_price, 2)}"
                last_win = True
            else:
                last_trade["status"] = "Loss"
                last_trade["pnl"] = f"{round(entry_price - curr_price, 2)}"
            
            last_trade["exit_price"] = curr_price
            last_trade["exit_time"] = get_beijing_time().strftime('%Y-%m-%d %H:%M')

    # 3. 计算总胜率
    total_closed = len([t for t in history if t.get("status") != "Pending"])
    total_wins = len([t for t in history if t.get("status") == "Win"])
    win_rate = round((total_wins / total_closed * 100), 1) if total_closed > 0 else 0

    return history, win_rate, total_wins, total_closed

def call_deepseek(news, market):
    """请求 AI 策略"""
    url = "https://api.deepseek.com/chat/completions"
    prompt = f"""
    实时金价: ¥{market['price_cny']}/克。新闻: "{news}"。
    请严格输出 JSON 格式策略：
    {{"direction": "做多/做空/观望", "reason": "简短理由", "confidence": "0-100"}}
    注意：不要输出Markdown，只输出纯JSON。
    """
    try:
        # 使用 V3 极速版保证响应，R1 容易超时适合手动复盘
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}"}
        resp = requests.post(url, json=payload, headers=headers).json()
        content = resp['choices'][0]['message']['content']
        # 清洗可能存在的 markdown 符号
        content = content.replace("```json", "").replace("```", "")
        return json.loads(content)
    except:
        return {"direction": "观望", "reason": "AI分析失败", "confidence": 0}

def run_task():
    print("🚀 启动胜率统计引擎...")
    market = get_sina_market()
    if not market: return

    # 1. 结算旧账，算胜率
    history, win_rate, wins, total = manage_ledger(market)
    print(f"🏆 当前战绩: {wins}/{total} (胜率 {win_rate}%)")

    # 2. 获取新闻并预测
    feed = feedparser.parse(RSS_URL)
    news_title = feed.entries[0].title if feed.entries else "无重大新闻"
    
    strategy = call_deepseek(news_title, market)
    
    # 3. 记录新一笔交易 (如果不是观望)
    if strategy["direction"] != "观望":
        new_trade = {
            "entry_time": get_beijing_time().strftime('%Y-%m-%d %H:%M'),
            "entry_price": market["price_cny"],
            "direction": strategy["direction"],
            "news": news_title[:50],
            "reason": strategy["reason"],
            "status": "Pending"
        }
        history.append(new_trade)
        # 只保留最近 50 条记录，防止文件无限变大
        if len(history) > 50: history.pop(0)
    
    # 4. 保存账本 (关键步骤)
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    # 5. 推送微信
    send_wechat(market, win_rate, total, strategy)

def send_wechat(market, win_rate, total_trades, strategy):
    url = "http://www.pushplus.plus/send"
    
    color = "#d32f2f" if strategy["direction"] == "做多" else "#2e7d32" if strategy["direction"] == "做空" else "#999"
    
    html = f"""
    <div style="font-family: Arial; padding: 15px; background: #fdfdfd; border-radius: 8px; border: 1px solid #eee;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <div style="font-size: 24px; font-weight: bold; color: #333;">¥{market['price_cny']}</div>
            <div style="text-align: right;">
                <div style="font-size: 10px; color: #999;">历史胜率 ({total_trades}场)</div>
                <div style="font-size: 18px; font-weight: 900; color: #d32f2f;">{win_rate}%</div>
            </div>
        </div>

        <div style="background: {color}; color: #fff; padding: 10px; text-align: center; border-radius: 4px; margin-bottom: 10px;">
            AI 信号: <b>{strategy['direction']}</b> (信心 {strategy.get('confidence',0)}%)
        </div>

        <div style="font-size: 14px; color: #555; line-height: 1.5;">
            💡 理由: {strategy['reason']}
        </div>
    </div>
    """
    requests.post(url, json={"token": PUSH_TOKEN, "title": f"胜率{win_rate}% | AI {strategy['direction']}", "content": html, "template": "html"})

if __name__ == "__main__":
    run_task()
