"""
Podcast to Article: 从小宇宙播客生成杂志风格文章
用法: python podcast_to_article.py <小宇宙单集URL或EpisodeID>

示例:
  python podcast_to_article.py https://www.xiaoyuzhoufm.com/episode/6123983acc5f215c6e0b7e6d
  python podcast_to_article.py 6123983acc5f215c6e0b7e6d
"""

import os
import re
import sys
import json
import requests
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()


def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("请设置 GEMINI_API_KEY 环境变量")
    return genai.Client(api_key=api_key)


def parse_episode_id(url_or_id):
    """从 URL 或纯 ID 中提取 episode ID"""
    match = re.search(r'episode/([a-f0-9]+)', url_or_id)
    if match:
        return match.group(1)
    # 纯 ID
    if re.match(r'^[a-f0-9]{24}$', url_or_id):
        return url_or_id
    raise ValueError(f"无法解析 episode ID: {url_or_id}")


def fetch_episode_info(episode_id):
    """从小宇宙网页抓取单集信息（标题、音频URL、shownotes）"""
    url = f"https://www.xiaoyuzhoufm.com/episode/{episode_id}"
    print(f"  正在获取: {url}")

    resp = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    }, timeout=30)
    resp.raise_for_status()

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        resp.text
    )
    if not match:
        raise RuntimeError("无法从页面提取数据，小宇宙可能更新了页面结构")

    data = json.loads(match.group(1))
    ep = data["props"]["pageProps"]["episode"]

    podcast = ep.get("podcast", {})
    enclosure = ep.get("enclosure", {})

    info = {
        "title": ep.get("title", ""),
        "podcast_name": podcast.get("title", ""),
        "shownotes": ep.get("shownotes", ""),
        "audio_url": enclosure.get("url", ""),
        "duration": ep.get("duration", 0),
        "episode_id": episode_id,
    }

    print(f"  标题: {info['title']}")
    print(f"  播客: {info['podcast_name']}")
    print(f"  时长: {info['duration'] // 60} 分钟")
    print(f"  音频: {info['audio_url'][:80]}...")

    return info


def download_audio(audio_url, episode_id):
    """下载音频文件"""
    ext = "m4a" if ".m4a" in audio_url else "mp3"
    filepath = f"podcast_{episode_id}.{ext}"

    if os.path.exists(filepath):
        size_mb = os.path.getsize(filepath) / 1024 / 1024
        print(f"  音频已存在: {filepath} ({size_mb:.1f} MB)，跳过下载")
        return filepath

    print(f"  正在下载音频...")
    resp = requests.get(audio_url, stream=True, timeout=300)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0

    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = downloaded / total * 100
                print(f"\r  下载中: {pct:.0f}% ({downloaded // 1024 // 1024} MB)", end="", flush=True)

    print(f"\n  下载完成: {filepath} ({downloaded // 1024 // 1024} MB)")
    return filepath


def transcribe_and_write(audio_path, episode_info):
    """用 Gemini 2.5 Flash 一步完成：转录音频 + 改写为文章"""
    client = get_gemini_client()

    print(f"  正在上传音频到 Gemini...")
    audio_file = client.files.upload(file=audio_path)
    print(f"  上传完成: {audio_file.uri}")

    # 等待文件处理完毕
    import time
    while audio_file.state.name == "PROCESSING":
        print(f"  等待处理中...")
        time.sleep(5)
        audio_file = client.files.get(name=audio_file.name)

    if audio_file.state.name == "FAILED":
        raise RuntimeError(f"音频处理失败: {audio_file.state}")

    prompt = f"""你是一位优秀的杂志作者。请完成以下两步任务：

**第一步：转录**
请将这段播客音频完整转录为中文文字。保留所有对话内容，标注不同说话者。

**第二步：改写**
基于转录内容，改写为一篇精心撰写的杂志风格长文。

播客信息：
- 标题：{episode_info['title']}
- 播客名：{episode_info['podcast_name']}
- 节目描述：{episode_info['shownotes'][:2000]}

改写要求：
- 用一个吸引人的标题开篇（不要直接用播客标题）
- 目标读者：聪明但非专业人士的普通读者
- 风格对标《三联生活周刊》或《人物》杂志的深度报道
- 高度可读、引人入胜，遇到术语要解释
- 提取关键洞见，尤其是反直觉的观点、生动的案例和令人意外的见解
- 保留重要的原话引用（清理口头禅和转录错误）
- 长度取决于原始内容的信息密度，自行判断，应该是一篇令人满足的长文
- 不要出现"在这期播客中"之类的表述——写成独立文章，读者无需听过播客
- 文末注明出处：「本文基于播客「{episode_info['podcast_name']}」单集「{episode_info['title']}」改写」

请先输出完整转录稿（用 <transcript> 标签包裹），然后输出改写后的文章。
文章用干净的 Markdown 格式。"""

    print(f"  正在让 Gemini 转录并改写（这可能需要几分钟）...")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_uri(
                file_uri=audio_file.uri,
                mime_type=audio_file.mime_type,
            ),
            prompt,
        ],
    )

    return response.text


def extract_article(text):
    """从 Gemini 输出中提取文章部分（去掉 <transcript> 标签内容）"""
    transcript_match = re.search(r'<transcript>(.*?)</transcript>', text, re.DOTALL)
    if transcript_match:
        return text[transcript_match.end():].strip()
    return text


def run(episode_input):
    """完整管线：解析 → 抓取 → 下载 → 转录改写 → 发邮件（含 EPUB）"""
    from send_email import send_newsletter

    print("=" * 60)
    print("播客 → 文章 (Gemini 2.5 Flash)")
    print("=" * 60)

    # Step 1: 解析 episode ID
    print("\n[1/5] 解析播客单集...")
    episode_id = parse_episode_id(episode_input)
    print(f"  Episode ID: {episode_id}")

    # Step 2: 获取单集信息
    print("\n[2/5] 获取单集信息...")
    episode_info = fetch_episode_info(episode_id)

    if not episode_info["audio_url"]:
        print("  ✗ 未找到音频链接")
        sys.exit(1)

    # Step 3: 下载音频
    print("\n[3/5] 下载音频...")
    audio_path = download_audio(episode_info["audio_url"], episode_id)

    # Step 4: Gemini 转录 + 改写
    print("\n[4/5] Gemini AI 转录 + 改写...")
    result_text = transcribe_and_write(audio_path, episode_info)
    article = extract_article(result_text)

    # Step 5: 发送邮件 + EPUB
    print("\n[5/5] 发送邮件...")
    episode_url = f"https://www.xiaoyuzhoufm.com/episode/{episode_id}"
    articles = [{
        "title": episode_info["title"],
        "channel": episode_info["podcast_name"],
        "url": episode_url,
        "article": article,
    }]
    send_newsletter(articles)

    # 清理音频文件
    if os.path.exists(audio_path):
        os.remove(audio_path)
        print(f"  已清理音频: {audio_path}")

    print("\n" + "=" * 60)
    print("✓ 完成！文章已发送到邮箱（含 EPUB）")
    print("=" * 60)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    run(sys.argv[1])


if __name__ == "__main__":
    main()
