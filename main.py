import requests
import feedparser
import os
import re
import time
from datetime import datetime, timedelta

# ---------------- 配置区 ----------------
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")
# 使用 CNBC 黄金/大宗商品专属源，确保资讯是全球最新的
RSS_URL = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"
# ---------------------------------------

def get_beijing_time():
    return datetime.utcnow() + timedelta(hours=8)

def get_realtime_market():
    """
    🔥 工业级数据源：新浪财经底层接口
    稳定、高速、包含伦敦金(美元)和离岸汇率
    """
    print("🚀 正在接入新浪底层数据链...")
    headers = {"Referer": "https://finance.sina.com.cn/"}
    
    # 失败重试机制
    for i in range(3):
        try:
            # hf_XAU: 伦敦金现货, fx_susdcny: 离岸人民币
            url = "http://hq.sinajs.cn/list=hf_XAU,fx_susdcny"
            resp = requests.get(url, headers=headers, timeout=5)
            content = resp.text
            
            # 1. 解析金价
            match_gold = re.search(r'hq_str_hf_XAU="([^"]+)"', content)
            if not match_gold: raise Exception("金价数据解析失败")
            gold_arr = match_gold.group(1).split(',')
            
            price_usd = float(gold_arr[0]) # 现价
            prev_close = float(gold_arr[7]) # 昨收
            
            if price_usd < 100: raise Exception("金价数据异常")

            # 2. 解析汇率
            match_rate = re.search(r'hq_str_fx_susdcny="([^"]+)"', content)
            rate_cny = 7.28 # 兜底
            if match_rate:
                rate_arr = match_rate.group(1).split(',')
                rate_cny = float(rate_arr[1])

            # 3. 计算
            price_cny = (price_usd * rate_cny) / 31.1035
            change_pct = (price_usd - prev_close) / prev_close * 100
            
            return {
                "price_usd": round(price_usd, 2),
                "price_cny": round(price_cny, 2),
                "change_pct": round(change_pct, 2),
                "rate_cny": rate_cny
            }
        except Exception as e:
            print(f"⚠️ 数据源波动 (第{i+1}次): {e}")
            time.sleep(1)
            
    print("❌ 严重错误：无法获取行情")
    return None

def call_ai_analyst(news_title, market):
    """
    🧠 双模大脑：优先 R1 推理，失败自动降级 V3
    """
    print(f"🧠 正在请求华尔街分析师...")
    url = "https://api.deepseek.com/chat/completions"
    
    # 极度专业的 Prompt
    prompt = f"""
    你现在是华尔街顶尖的宏观对冲基金经理（如瑞达利欧风格）。
    
    【实时盘面】:
    - 标的: 伦敦金(XAU/USD)
    - 现价: ${market['price_usd']} (折合 ¥{market['price_cny']}/克)
    - 涨跌: {market['change_pct']}%
    - 突发新闻: "{news_title}"
    
    请进行【深度推理】，并输出一份《实战交易指令》。
    
    必须严格包含以下 3 个部分（不要废话）：
    
    1. 🚦 **交易信号**：
       - 【做多 Long】 / 【做空 Short】 / 【观望 Wait】
       - 胜率预估：X% (必须给出数值)
       - 理由：一句话概括核心逻辑（例如：美债收益率背离、避险情绪升温）。

    2. 🎯 **关键点位 (CNY/克)**：
       - 进场位：¥___
       - 止损位：¥___ (必须严格给出)
       - 止盈位：¥___

    3. 🕵️ **预期差分析**：
       - 市场现在在交易什么预期？这条新闻是否已经被 Price-in？
    """

    # 优先尝试 R1 (推理模型)
    try:
        print("尝试调用 DeepSeek-R1 (深度思考)...")
        payload = {
            "model": "deepseek-reasoner",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1 # 极度严谨
        }
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_KEY}"}
        resp = requests.post(url, json=payload, headers=headers, timeout=60) # R1 比较慢，给60秒
        
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content'], "DeepSeek-R1 (深度推理)"
    except Exception as e:
        print(f"⚠️ R1 调用失败: {e}，准备切换备用模型...")

    # 降级尝试 V3 (极速模型)
    try:
        print("降级调用 DeepSeek-V3 (极速响应)...")
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content'], "DeepSeek-V3 (极速版)"
    except Exception as e:
        return f"AI 暂时离线，请人工盯盘。错误: {e}", "系统离线"
        
    return "AI 未返回有效数据", "未知错误"

def send_wechat(title, content, market, model_name, link):
    url = "http://www.pushplus.plus/send"
    bj_time = get_beijing_time().strftime('%H:%M')
    
    # 配色：涨红跌绿
    is_up = market['change_pct'] >= 0
    bg_color = "#d32f2f" if is_up else "#2e7d32"
    arrow = "📈" if is_up else "📉"
    
    # 格式化内容
    content_html = content.replace("\n", "<br>").replace("**", "")
    
    html = f"""
    <div style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
        <div style="background: {bg_color}; color: #fff; padding: 20px; text-align: center;">
            <div style="font-size: 14px; opacity: 0.8;">人民币现货金价</div>
            <div style="font-size: 36px; font-weight: bold; margin: 5px 0;">¥{market['price_cny']}</div>
            <div style="font-size: 14px;">
                国际 ${market['price_usd']} | {arrow} {market['change_pct']}%
            </div>
        </div>
        
        <div style="padding: 15px; background: #fff;">
            <div style="font-size: 12px; color: #999; margin-bottom: 10px; display: flex; justify-content: space-between;">
                <span>🧠 策略大脑: {model_name}</span>
                <span>🕒 {bj_time}</span>
            </div>
            
            <div style="font-weight: bold; font-size: 16px; color: #333; margin-bottom: 10px;">
                📰 {title}
            </div>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; font-size: 15px; line-height: 1.6; color: #333; border-left: 4px solid {bg_color};">
                {content_html}
            </div>
        </div>
        
        <a href="{link}" style="display: block; text-align: center; background: #eee; color: #555; padding: 10px; text-decoration: none; font-size: 12px;">
            查看 CNBC 原始数据源
        </a>
    </div>
    """
    
    # 标题带上价格，不点开也能看
    push_title = f"{arrow} ¥{market['price_cny']} 策略发出"
    requests.post(url, json={"token": PUSH_TOKEN, "title": push_title, "content": html, "template": "html"})

def run_task():
    print("🚀 启动最终版黄金监测系统...")
    
    # 1. 获取行情 (死命令：必须成功)
    market = get_realtime_market()
    if not market:
        print("💥 致命错误：数据源全线崩溃")
        return

    print(f"✅ 锁定金价: ${market['price_usd']} (¥{market['price_cny']})")

    try:
        # 2. 获取新闻
        feed = feedparser.parse(RSS_URL)
        if len(feed.entries) > 0:
            entry = feed.entries[0]
            print(f"📰 最新资讯: {entry.title}")
            
            # 3. 执行分析 (R1 -> V3)
            ai_res, model_used = call_ai_analyst(entry.title, market)
            
            # 4. 推送
            send_wechat(entry.title, ai_res, market, model_used, entry.link)
            print("✅ 策略已推送成功！")
        else:
            print("📭 暂时没有重大新闻，但行情监控正常。")
            # 也可以选择这里强制推送一条纯盘面分析，看你需求
            
    except Exception as e:
        print(f"❌ 运行报错: {e}")

if __name__ == "__main__":
    run_task()
