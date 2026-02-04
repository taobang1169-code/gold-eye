import requests
import feedparser
import os
import json
import time

# 读取两把钥匙
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")

def call_deepseek_analysis(news_title, news_link):
    """【核心功能】调用 DeepSeek 大脑进行分析"""
    print(f"正在请求 DeepSeek 分析: {news_title} ...")
    
    url = "https://api.deepseek.com/chat/completions"
    
    # 这里是让 AI 扮演角色的指令
    prompt = f"""
    你是拥有20年经验的专业宏观交易员。
    请阅读这条最新的全球财经新闻："{news_title}"
    
    请输出一份简短的中文情报（不要废话，直接给结论）：
    1. 【核心事件】：一句话概括发生了什么。
    2. 【黄金/A股影响】：判断是利多、利空还是中性？
    3. 【逻辑】：用最通俗的话解释为什么。
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a professional financial analyst."},
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
        result = response.json()
        if 'choices' in result:
            return result['choices'][0]['message']['content']
        else:
            return "AI 思考超时，请直接看原文。"
    except Exception as e:
        print(f"请求 AI 失败: {e}")
        return "AI 接口连接失败。"

def send_wechat(title, content, link):
    """发送到微信"""
    url = "http://www.pushplus.plus/send"
    
    html_content = f"""
    <h3>🤖 黄金之眼 (DeepSeek版)</h3>
    <hr>
    {content.replace(chr(10), '<br>')} 
    <hr>
    <p><small>原文标题: {title}</small></p>
    <a href='{link}'>👉 点击阅读原文</a>
    """
    
    data = {
        "token": PUSH_TOKEN,
        "title": "⚡ 关键情报分析",
        "content": html_content,
        "template": "html"
    }
    requests.post(url, json=data)

def run_task():
    # CNBC 国际版 RSS
    rss_url = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"
    
    try:
        print("正在扫描华尔街新闻...")
        feed = feedparser.parse(rss_url)
        
        # 每次只分析最新的一条
        if len(feed.entries) > 0:
            entry = feed.entries[0]
            print(f"发现最新新闻: {entry.title}")
            
            # 关键词过滤
            keywords = ["Gold", "Fed", "China", "Rate", "Inflation", "Dollar", "Trump", "Bitcoin"]
            
            if any(k in entry.title for k in keywords):
                print(">>> 命中关键词！启动 AI 分析...")
                ai_analysis = call_deepseek_analysis(entry.title, entry.link)
                send_wechat(entry.title, ai_analysis, entry.link)
                print("推送完成。")
            else:
                print(">>> 新闻平平无奇，跳过。")
        else:
            print("暂时无法获取新闻流。")
            
    except Exception
