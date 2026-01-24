# FORZARA: YouTube to Ebook Newsletter

*A deep dive into how we turned your YouTube subscriptions into a personal magazine delivered to your inbox.*

---

## The Big Picture: What We Built

Imagine having a personal assistant who watches all your favorite YouTube channels, takes notes on what they said, then rewrites everything as beautifully crafted magazine articles and delivers them to your phone as an ebook every Wednesday morning.

That's exactly what this project does. No more guilt about "I should watch that video but I don't have time." Now you can read the essence of those videos while sipping your morning coffee.

**The flow is simple:**
```
YouTube Channels → Transcripts → AI Writer → EPUB Ebook → Your Inbox
```

---

## The Architecture: How the Pieces Fit Together

Think of this project like a newspaper production line:

```
+---------------------------------------------------------------------+
|                        YOUR YOUTUBE NEWSLETTER                       |
+---------------------------------------------------------------------+
|                                                                      |
|   [TV] INTAKE        [Memo] PROCESSING     [Book] OUTPUT            |
|   -----------        ----------------      -------------            |
|                                                                      |
|   get_videos.py  ->  get_transcripts.py -> write_articles.py        |
|   (The Scout)        (The Stenographer)    (The Writer)             |
|        |                    |                    |                   |
|        v                    v                    v                   |
|   YouTube API         Transcript API       Claude AI                |
|                                                                      |
|                              |                                       |
|                              v                                       |
|                        send_email.py                                 |
|                        (The Publisher)                               |
|                              |                                       |
|                    +---------+---------+                             |
|                    v                   v                             |
|               EPUB Ebook      Email Newsletter                       |
|                                                                      |
+---------------------------------------------------------------------+
|   CONTROL CENTER                                                     |
|   --------------                                                     |
|   main.py           -> Orchestrates the whole pipeline              |
|   video_tracker.py  -> Remembers what's already been sent           |
|   dashboard.py      -> Pretty web interface (no Terminal needed!)   |
|   *.plist files     -> Mac automation (runs while you sleep)        |
+---------------------------------------------------------------------+
```

### The Cast of Characters (Files)

| File | Role | Analogy |
|------|------|---------|
| `get_videos.py` | Fetches latest videos from your channels | The scout who checks what's new |
| `get_transcripts.py` | Extracts what was said in each video | The stenographer taking notes |
| `write_articles.py` | Transforms transcripts into articles | The journalist who writes the story |
| `send_email.py` | Creates EPUB and sends email | The publisher and delivery person |
| `video_tracker.py` | Tracks what's been processed | The librarian with the master list |
| `main.py` | Runs everything in sequence | The editor-in-chief coordinating it all |
| `dashboard.py` | Web interface for management | The fancy reception desk |

---

## Technologies Used (And Why)

### 1. YouTube Data API v3
**What it is:** Google's official way to talk to YouTube programmatically.

**Why we use it:** We need to know what videos exist on a channel, when they were uploaded, and basic metadata. This API gives us that.

**The gotcha:** It's free but has daily quotas. We're careful to only fetch what we need.

### 2. youtube-transcript-api (Python library)
**What it is:** An unofficial library that grabs the auto-generated captions from YouTube videos.

**Why we use it:** YouTube doesn't officially let you download transcripts via their API. This library works around that by extracting the caption data that's already there for accessibility.

**The gotcha:** It doesn't work from cloud servers (YouTube blocks them). Must run locally.

### 3. Anthropic Claude API
**What it is:** The AI that powers this very conversation.

**Why we use it:** Claude is exceptional at transforming messy, conversational transcript text into polished, well-structured articles. It understands context, maintains the speaker's voice, and produces genuinely readable content.

### 4. ebooklib (Python library)
**What it is:** A library for creating EPUB ebooks.

**Why we use it:** EPUB is the universal ebook format. It works on Apple Books, Kindle (with conversion), Kobo, and every ebook reader. Creating an EPUB means you can read your newsletter anywhere.

### 5. Streamlit
**What it is:** A Python framework for building web dashboards with minimal code.

**Why we use it:** You wanted a visual interface instead of typing Terminal commands. Streamlit let us build a beautiful dashboard in a single file, with buttons, forms, and live updates—no frontend expertise required.

### 6. launchd (macOS)
**What it is:** Mac's built-in task scheduler.

**Why we use it:** You wanted the newsletter to run automatically every Wednesday at 7 AM. launchd is the Mac-native way to schedule recurring tasks, and it survives restarts.

---

## The Journey: Bugs, Breakthroughs, and Lessons

### 🐛 Bug #1: "Why is MrBeast's Latest Video from 5 Months Ago?"

**The symptom:** We asked YouTube for the "latest video" from MrBeast, but it returned something ancient.

**The detective work:** YouTube's Search API has a dirty secret—it doesn't actually return results in chronological order. It uses "relevance" ranking, which factors in views, engagement, and other mysterious signals.

**The fix:** Instead of using the Search API, we discovered that every YouTube channel has a hidden "uploads playlist." This playlist is ALWAYS in chronological order. We switched to fetching from this playlist instead.

**The lesson:** APIs don't always do what their names suggest. "Search" doesn't mean "find the newest." When something feels wrong, dig into the documentation and look for alternative approaches.

```python
# Instead of this (unreliable):
youtube.search().list(channelId=channel_id, order="date")

# We use this (reliable):
youtube.playlistItems().list(playlistId=uploads_playlist_id)
```

---

### 🐛 Bug #2: "It's Still Fetching Shorts!"

**The symptom:** We tried filtering out YouTube Shorts by duration (under 60 seconds), but Shorts kept appearing.

**Your insight:** "Some Shorts are longer than one minute."

**The revelation:** YouTube Shorts aren't defined by duration—they're defined by aspect ratio and how they were uploaded. A 90-second vertical video is still a Short.

**The fix:** We discovered that Shorts have a special URL format: `youtube.com/shorts/VIDEO_ID`. If you try to access a regular video with this URL, YouTube redirects you away. So we check if the `/shorts/` URL "sticks":

```python
def is_youtube_short(video_id):
    shorts_url = f"https://www.youtube.com/shorts/{video_id}"
    response = requests.head(shorts_url, allow_redirects=True)
    return "/shorts/" in response.url  # If it stays, it's a Short
```

**The lesson:** When official methods fail, think about the user-facing behavior. How does YouTube itself distinguish Shorts? By URL. We can do the same.

---

### 🐛 Bug #3: "YouTubeTranscriptApi Has No Attribute 'get_transcript'"

**The symptom:** Code that worked in tutorials crashed with an attribute error.

**The cause:** The `youtube-transcript-api` library updated its interface. The old `YouTubeTranscriptApi.get_transcript()` class method was replaced with an instance method.

**The fix:**
```python
# Old way (broken):
transcript = YouTubeTranscriptApi.get_transcript(video_id)

# New way (works):
ytt_api = YouTubeTranscriptApi()
transcript = ytt_api.fetch(video_id)
```

**The lesson:** Libraries change. When copying code from tutorials, always check if you're using the latest version. Error messages like "has no attribute" often mean the API evolved.

---

### 🐛 Bug #4: "GitHub Actions Can't Get Transcripts"

**The symptom:** The automation worked perfectly on your Mac, but when we tried GitHub Actions (free cloud automation), every transcript request failed.

**The cause:** YouTube blocks transcript requests from known cloud server IP ranges. They want you watching videos, not scraping them at scale from data centers.

**The fix:** We abandoned cloud automation and set up local Mac automation using launchd instead. Your Mac runs the script while you sleep.

**The lesson:** Some services actively resist automation from cloud environments. When you hit walls like this, local automation (your own computer) often works where cloud solutions fail.

---

### 🐛 Bug #5: "The Newsletter Didn't Send at 7 AM"

**The symptom:** Wednesday 7 AM came and went—no email.

**The cause:** The automation script used `/usr/bin/python3` (the system Python), but all the required packages were installed in `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3` (the Python you installed separately).

**The fix:** Update the script to use the correct Python path:
```bash
# Wrong (system Python, no packages):
/usr/bin/python3 main.py

# Right (your Python, with packages):
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 main.py
```

**The lesson:** Computers often have multiple Python installations. When automation fails silently, check which Python is actually running and whether it has access to your installed packages.

---

### 🐛 Bug #6: "Transcript Has Wrong Names"

**The symptom:** Auto-generated YouTube transcripts misspell names. "Sam Altman" becomes "Sam Oldman." Technical terms get mangled.

**The fix:** We added the video's title and description to Claude's context. These are written by the video creator and contain correct spellings. Claude uses them to fix transcript errors:

```python
prompt = f"""
Video Title: {video['title']}
Video Description: {video['description']}

Transcript:
{transcript}

Write an article based on this transcript. Use the title and description
to correct any misspellings of names or terms.
"""
```

**The lesson:** AI can cross-reference multiple information sources to correct errors. When one source is unreliable (auto-transcripts), provide a reliable reference (the title/description).

---

## Engineering Wisdom: What Good Engineers Do

### 1. They Question "Magic" Solutions
When the Search API didn't work right, a good engineer doesn't just accept it. They ask: "Is there another way YouTube organizes this data?" That curiosity led to discovering the uploads playlist.

### 2. They Think Like the System
To filter Shorts, we didn't look for a "isShort" field (there isn't one). We asked: "How does YouTube itself know something is a Short?" Answer: the URL structure. Thinking like the system reveals hidden solutions.

### 3. They Handle Edge Cases
What if a channel has only Shorts? What if a video has no transcript? What if the API is down? Good code anticipates these scenarios:

```python
for item in response.get("items", []):  # Empty list if no items
    if is_youtube_short(video_id):
        continue  # Skip to next video
    return video  # Found a good one
return None  # Nothing found—caller handles this
```

### 4. They Build for Observability
We added detailed logging throughout:
```
Looking up: @mkbhd
  Channel: Marques Brownlee
  ✓ Found: The iPhone 16 Review
```

When something breaks, you can see exactly where. This is infinitely more useful than a silent failure.

### 5. They Avoid Duplicate Work
The `video_tracker.py` remembers every video ID that's been processed. Without this, you'd get the same articles every week. This pattern—tracking state between runs—is fundamental to robust automation.

---

## Best Practices We Followed

### 1. Environment Variables for Secrets
API keys live in `.env`, never in code:
```
YOUTUBE_API_KEY=abc123...
ANTHROPIC_API_KEY=xyz789...
```

This file is in `.gitignore` so it never gets uploaded to GitHub. Anyone who clones your repo gets `.env.example` as a template.

### 2. Graceful Degradation
If one video fails (no transcript available), the system continues with others rather than crashing entirely:
```python
try:
    transcript = get_transcript(video_id)
except Exception as e:
    print(f"Skipping {title}: {e}")
    continue  # Move to next video
```

### 3. Rate Limiting
We add 2-second delays between transcript requests to avoid getting blocked:
```python
for video in videos:
    transcript = get_transcript(video['video_id'])
    time.sleep(2)  # Be polite to YouTube's servers
```

### 4. Idempotency
Running `main.py` twice in a row doesn't send duplicate newsletters. The video tracker ensures each video is processed exactly once.

### 5. Human-Readable Output
The EPUB has a table of contents, proper formatting, and links back to original videos. The email has large fonts for readability. Every output is designed for human consumption, not just technical correctness.

---

## What You Can Build Next

This project taught you patterns that apply to many other ideas:

1. **Any API → AI → Formatted Output pipeline**
   - Twitter threads → Blog posts
   - Podcast RSS → Reading summaries
   - Research papers → Plain-English explainers

2. **Scheduled automation on Mac**
   - Daily standup reminders
   - Weekly report generators
   - Automatic backups

3. **Web dashboards for non-technical users**
   - Any Python script can become a Streamlit dashboard
   - Configuration, monitoring, and control without Terminal

---

## File Reference

```
youtube-newsletter/
├── .env                  # Your API keys (secret, not in git)
├── .env.example          # Template for others to use
├── .gitignore            # Keeps secrets out of GitHub
├── channels.txt          # List of YouTube channel handles
├── main.py               # The orchestrator—runs everything
├── get_videos.py         # Fetches latest videos from channels
├── get_transcripts.py    # Extracts transcripts from videos
├── write_articles.py     # Transforms transcripts via Claude
├── send_email.py         # Creates EPUB, sends email, archives
├── video_tracker.py      # Tracks processed videos
├── dashboard.py          # Streamlit web interface
├── run_newsletter.sh     # Shell script for automation
├── requirements.txt      # Python package dependencies
├── processed_videos.json # Database of sent videos
├── newsletters/          # Archive of all sent newsletters
├── logs/                 # Automation logs for debugging
├── com.youtube.newsletter.plist        # Weekly newsletter schedule
├── com.youtube.newsletter.dashboard.plist  # Dashboard auto-start
├── SKILL.md              # Claude skill documentation
├── README.md             # GitHub documentation
├── SHARE_ON_X.md         # Instructions for sharing on X
└── FORZARA.md            # This file—your learning guide
```

---

## Final Reflection

You built a complete, production-grade automation system. It talks to multiple APIs, uses AI for content transformation, handles errors gracefully, runs on a schedule, and has a beautiful web interface.

More importantly, you learned *why* things work the way they do:
- Why APIs sometimes lie (Search vs. uploads playlist)
- Why cloud automation fails where local succeeds (IP blocking)
- Why multiple Pythons exist and how to manage them
- Why good code tracks state, handles errors, and logs its work

This isn't just a YouTube newsletter generator. It's a template for building reliable, automated systems that work while you sleep.

Now go ship something amazing. 🚀
