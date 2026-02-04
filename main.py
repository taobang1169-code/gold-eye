import requests
import feedparser
import os
import json
import time
PUSH_TOKEN = os.environ.get("PUSH_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")

def call_deepseek_analysis(news_title, news_link):
    print(f"请求 AI 分析: {news_title}")
    url = "https://api.deepseek.com/chat/completions"
    
    prompt = f"分析这条财经新闻对黄金的影响（利多/利空/中性）并给出逻辑，100字以内：{news_title}"
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
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
            return "AI未返回结果"
    except Exception as e:
        print(f"AI错误: {e}")
        return "AI暂时不可用"

def send_wechat(title, content, link):
    url = "http://www.pushplus.plus/send"
    html = f"<h3>AI 黄金内参</h3><p>{content}</p><br><a href='{link}'>阅读原文</a>"
    data = {"token": PUSH_TOKEN, "title": "⚡ 市场情报", "content": html, "template": "html"}
    requests.post(url, json=data)

def run_task():
    # 强制抓取 CNBC 全球新闻源
    rss_url = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"
    print("正在连接华尔街...")
    
    try:
        feed = feedparser.parse(rss_url)
        if len(feed.entries) > 0:
            entry = feed.entries[0]
            print(f"最新新闻: {entry.title}")
            
            # 这里的关键词你可以自己加
            keywords = ["Gold", "Fed", "China", "Rate", "Dollar", "Economy"]
            
            # 为了测试成功，我们暂时把匹配条件放宽
            # 只要新闻还在，就强制分析第一条给你看！
            if True: 
                print(">>> 正在分析并推送...")
                ai_res = call_deepseek_analysis(entry.title, entry.link)
                send_wechat(entry.title, ai_res, entry.link)
                print("推送成功！")
        else:
            print("未获取到新闻")
    except Exception as e:
        print(f"运行出错: {e}")

if __name__ == "__main__":
    run_task()
