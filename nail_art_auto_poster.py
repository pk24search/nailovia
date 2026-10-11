import feedparser
import os
import re
import time
import hashlib
import requests
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ==========================================
# CONFIGURATIONS
# ==========================================

GEMINI_API_KEYS = os.environ.get("GEMINI_API_KEYS", "").split(",")
GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
]

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

CLIENT_ID = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")
REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN", "")
BLOG_ID = os.environ.get("BLOG_ID", "")
YOUR_BLOG_URL = os.environ.get("BLOG_URL", "https://yournailart.blogspot.com")

# ==========================================
# FEEDS (Nail Art Categories)
# ==========================================
FEEDS = {
    "Nail Art Trends": "https://www.scratchmagazine.co.uk/feed/",
    "Nail Trends & News": "https://www.bangstyle.com/feed/",
    "Nail Design Ideas": "https://www.themilliondollarmama.com/feed/",
    "Simple Nail Designs": "https://nailsblaze.com/feed/",
    "Nail Care & Health": "https://www.organicauthority.com/tag/nail/feed",
    "Nail Art Inspiration": "https://pak.net.pk/tag/nail-art/feed/",
    "Nail Tutorials & Guides": "https://choosynails.com/feed/",
    "Nail Trends Gallery": "https://mirelleinspo.com/feed/",
    "Nail Design & Art": "https://www.nailsmag.com/feed/",
    "Beauty & Nail Trends": "https://www.refinery29.com/feed/",
    "Fashion & Nail Trends": "https://www.vogue.com/feed/",
    "Entertainment & Nail Art": "https://dailyshowbiz.net/feed/",
}

LABEL_MAP = {
    "Nail Art Trends": "Nail Art Trends",
    "Nail Trends & News": "Nail Trends & News",
    "Nail Design Ideas": "Nail Design Ideas",
    "Simple Nail Designs": "Simple Nail Designs",
    "Nail Care & Health": "Nail Care & Health",
    "Nail Art Inspiration": "Nail Art Inspiration",
    "Nail Tutorials & Guides": "Nail Tutorials & Guides",
    "Nail Trends Gallery": "Nail Trends Gallery",
    "Nail Design & Art": "Nail Design & Art",
    "Beauty & Nail Trends": "Beauty & Nail Trends",
    "Fashion & Nail Trends": "Fashion & Nail Trends",
    "Entertainment & Nail Art": "Entertainment & Nail Art",
}

POSTED_URLS_FILE = "posted_urls.txt"
POSTED_TITLES_FILE = "posted_titles.txt"
POSTED_IMAGES_FILE = "posted_images.txt"
POSTED_HASHES_FILE = "posted_hashes.txt"

# Keywords to filter nail-related posts
NAIL_KEYWORDS = [
    "nail", "nails", "manicure", "pedicure", "polish", "gel",
    "acrylic", "lacquer", "cuticle", "nail art", "nail design"
]

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def load_set_from_file(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_to_file(filename, value):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(value + "\n")

def load_posted_urls():
    return load_set_from_file(POSTED_URLS_FILE)

def load_posted_titles():
    return load_set_from_file(POSTED_TITLES_FILE)

def load_posted_images():
    return load_set_from_file(POSTED_IMAGES_FILE)

def load_posted_hashes():
    return load_set_from_file(POSTED_HASHES_FILE)

def save_posted_url(url):
    save_to_file(POSTED_URLS_FILE, url)

def save_posted_title(title):
    save_to_file(POSTED_TITLES_FILE, title)

def save_posted_image(image_url):
    save_to_file(POSTED_IMAGES_FILE, image_url)

def save_posted_hash(h):
    save_to_file(POSTED_HASHES_FILE, h)

def normalize_title(title):
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip().lower()
    return title

def content_hash(text):
    if not text:
        return ""
    snippet = re.sub(r'\s+', '', text[:200]).strip().lower()
    return hashlib.md5(snippet.encode('utf-8')).hexdigest()

def has_english_letters(text):
    if not text:
        return False
    return bool(re.search(r'[A-Za-z]', text))

def has_non_english_script(text):
    """Check if text contains non-English scripts like Urdu, Arabic, Hindi, etc."""
    if not text:
        return True
    bad_ranges = [
        (0x0600, 0x06FF),  # Arabic / Urdu
        (0x0750, 0x077F),  # Arabic Supplement
        (0x0900, 0x097F),  # Devanagari
        (0x0980, 0x09FF),  # Bengali
        (0x0A00, 0x0A7F),  # Gurmukhi
        (0x0A80, 0x0AFF),  # Gujarati
        (0x0B00, 0x0B7F),  # Oriya
        (0x0B80, 0x0BFF),  # Tamil
        (0x0C00, 0x0C7F),  # Telugu
        (0x0C80, 0x0CFF),  # Kannada
        (0x0D00, 0x0D7F),  # Malayalam
        (0x0D80, 0x0DFF),  # Sinhala
        (0x0E00, 0x0E7F),  # Thai
        (0x0E80, 0x0EFF),  # Lao
        (0x4E00, 0x9FFF),  # CJK
    ]
    for char in text:
        code = ord(char)
        for start, end in bad_ranges:
            if start <= code <= end:
                return True
    return False

def is_nail_related(title, text):
    combined = (title + " " + (text or "")).lower()
    return any(keyword in combined for keyword in NAIL_KEYWORDS)

# ==========================================
# GEMINI FUNCTION
# ==========================================

def get_gemini_response(prompt):
    for model in GEMINI_MODELS:
        print("Gemini trying: " + model)
        for key in GEMINI_API_KEYS:
            key = key.strip()
            if not key:
                continue
            try:
                url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + key
                headers = {'Content-Type': 'application/json'}
                data = {"contents": [{"parts": [{"text": prompt}]}]}
                response = requests.post(url, headers=headers, json=data, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        print("Gemini success: " + model)
                        return result['candidates'][0]['content']['parts'][0]['text'].strip()
                elif response.status_code == 429:
                    print("Gemini quota khatam: " + model)
                else:
                    print("Gemini " + model + " failed: " + str(response.status_code))
                time.sleep(1)
            except Exception as e:
                print("Gemini network error: " + str(e))
                time.sleep(1)
    print("Gemini saare fail.")
    return None

# ==========================================
# GROQ FUNCTION
# ==========================================

def get_groq_response(prompt):
    if not GROQ_API_KEY:
        print("Groq key nahi hai. Skip.")
        return None
    print("Groq trying: " + GROQ_MODEL)
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": "Bearer " + GROQ_API_KEY, "Content-Type": "application/json"}
        data = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional English content writer. You ONLY output the final English result in the exact requested format. You NEVER explain, reason, think out loud, or write your thoughts. You NEVER use placeholders like [English Title Here]."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 3000
        }
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            print("Groq success: " + GROQ_MODEL)
            return content
        elif response.status_code == 429:
            print("Groq quota khatam.")
        else:
            print("Groq failed: " + str(response.status_code))
    except Exception as e:
        print("Groq network error: " + str(e))
    return None

# ==========================================
# OPENROUTER FUNCTION
# ==========================================

def get_openrouter_response(prompt):
    if not OPENROUTER_API_KEY:
        print("OpenRouter key nahi hai. Skip.")
        return None
    print("OpenRouter trying: " + OPENROUTER_MODEL)
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": "Bearer " + OPENROUTER_API_KEY,
            "Content-Type": "application/json",
            "HTTP-Referer": YOUR_BLOG_URL,
            "X-Title": "Nail Art Blog"
        }
        data = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional English content writer. You ONLY output the final English result in the exact requested format. You NEVER explain, reason, think out loud, or write your thoughts. You NEVER use placeholders like [English Title Here]."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 3000
        }
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            print("OpenRouter success: " + OPENROUTER_MODEL)
            return content
        elif response.status_code == 429:
            print("OpenRouter quota khatam.")
        else:
            print("OpenRouter failed: " + str(response.status_code))
    except Exception as e:
        print("OpenRouter network error: " + str(e))
    return None

# ==========================================
# MASTER AI FUNCTION
# ==========================================

def get_ai_response(prompt):
    print("=" * 50)
    print("Step 1: Gemini")
    response = get_gemini_response(prompt)
    if response:
        return response
    print("Step 2: Groq")
    response = get_groq_response(prompt)
    if response:
        return response
    print("Step 3: OpenRouter")
    response = get_openrouter_response(prompt)
    if response:
        return response
    print("Saare providers fail ho gaye.")
    return None

# ==========================================
# PROMPT BUILDER (English Rewrite)
# ==========================================

def build_prompt(source_title, original_content, strict_mode=False):
    prompt = "TASK: Rewrite the following nail art news/article in original English.\n\n"
    prompt += "INPUT TITLE:\n"
    prompt += source_title + "\n\n"
    prompt += "INPUT ARTICLE:\n"
    prompt += original_content + "\n\n"
    prompt += "RULES:\n"
    prompt += "- Output ONLY the final result. Do NOT write your thinking, reasoning, or explanation.\n"
    prompt += "- Do NOT repeat the instructions. Do NOT write 'We need to...' or 'Let me...'.\n"
    prompt += "- Do NOT use placeholders like [English Title Here] or [English Content Here].\n"
    prompt += "- Output MUST be 100% English. Do NOT use Urdu, Arabic, Hindi, or any other script.\n"
    prompt += "- Keep facts, numbers, and names unchanged.\n"
    prompt += "- Make it engaging, SEO-friendly, and suitable for a nail art blog.\n"
    prompt += "- Keep the article concise but informative.\n\n"

    if strict_mode:
        prompt += "!!!!! EXTREME WARNING !!!!!\n"
        prompt += "Your previous response was REJECTED because it contained non-English text or placeholders.\n"
        prompt += "This time, output ONLY the final English result in the exact format below.\n\n"

    prompt += "OUTPUT FORMAT (follow exactly, nothing else):\n"
    prompt += "TITLE: <english title here>\n"
    prompt += "CONTENT: <english content here>\n"
    return prompt

# ==========================================
# AI PROCESSING FUNCTION
# ==========================================

def parse_ai_response(response):
    if not response:
        return None, None

    response_lower = response.lower()
    garbage_signs = [
        "we need to", "let's see", "let me", "wait,", "actually", "we must",
        "[english title here]", "[english content here]",
        "task:", "input title:", "input article:", "rules:", "output format:",
        "here is the", "here's the",
    ]
    for sign in garbage_signs:
        if sign in response_lower:
            print("Garbage detected in AI response: " + sign)
            return None, None

    try:
        if "TITLE:" in response and "CONTENT:" in response:
            parts = response.split("CONTENT:", 1)
            title_part = parts[0].replace("TITLE:", "").strip()
            content_part = parts[1].strip()
            title_part = title_part.replace("TITLE:", "").strip()
            return (title_part if title_part else None, content_part if content_part else None)
        else:
            print("AI response format invalid (missing TITLE/CONTENT markers)")
            return None, None
    except Exception as e:
        print("Parse error: " + str(e))
        return None, None

def process_content_with_ai(source_title, original_content):
    final_title = source_title
    final_content = None
    last_response = None

    for attempt in range(3):
        print("AI Attempt " + str(attempt + 1) + "/3")
        strict = (attempt > 0)
        prompt = build_prompt(source_title, original_content, strict_mode=strict)
        response = get_ai_response(prompt)
        if not response:
            print("AI ne jawab nahi diya. Retry...")
            time.sleep(2)
            continue

        last_response = response
        temp_title, temp_content = parse_ai_response(response)

        if not temp_title or not temp_content:
            print("Garbage response. Retrying...")
            time.sleep(2)
            continue

        temp_title = temp_title.strip()
        temp_content = temp_content.strip()

        title_has_bad = has_non_english_script(temp_title)
        content_has_bad = has_non_english_script(temp_content)
        title_has_english = has_english_letters(temp_title)
        content_has_english = has_english_letters(temp_content)

        if not title_has_bad and not content_has_bad and title_has_english and content_has_english and temp_content:
            final_title = temp_title
            final_content = temp_content
            print("English content valid.")
            break
        else:
            print("Bad characters detected! Retrying...")
            time.sleep(2)

    if not final_content and last_response:
        print("Teen attempts fail. Aakhri response clean kar rahe hain.")
        final_title, final_content = parse_ai_response(last_response)
        if final_title:
            final_title = final_title.strip()
        if final_content:
            final_content = final_content.strip()

    if not final_content:
        print("AI fail. Using original English content.")
        final_title = source_title
        final_content = original_content

    if not final_title:
        final_title = source_title

    return final_title, final_content

# ==========================================
# IMAGE OPTIMIZATION FUNCTION
# ==========================================

def optimize_image_tag(img_tag, is_lcp=True):
    if img_tag is None:
        return img_tag
    try:
        if is_lcp:
            img_tag['loading'] = 'eager'
            img_tag['fetchpriority'] = 'high'
        else:
            img_tag['loading'] = 'lazy'
            img_tag['fetchpriority'] = 'auto'

        img_tag['decoding'] = 'async'

        if not img_tag.get('width'):
            img_tag['width'] = '800'
        if not img_tag.get('height'):
            img_tag['height'] = '450'
        if not img_tag.get('alt'):
            img_tag['alt'] = 'Nail Art Image'
        if not img_tag.get('referrerpolicy'):
            img_tag['referrerpolicy'] = 'no-referrer'
    except Exception as e:
        print("Image optimize error: " + str(e))
    return img_tag

# ==========================================
# BLOGGER FUNCTION
# ==========================================

def post_to_blogger(title, content, labels_list):
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    try:
        service = build('blogger', 'v3', credentials=creds)
        body = {"title": title, "content": content, "labels": labels_list}
        posts = service.posts()
        res = posts.insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
        print("Blogger Post Published: " + res.get('url'))
        return res.get('url')
    except Exception as e:
        print("Blogger Post Error: " + str(e))
        return None

# ==========================================
# MAIN EXECUTION
# ==========================================

def fetch_and_post_news():
    print("Nail Art Auto Blogger Script Started!")
    posted_urls = load_posted_urls()
    posted_titles = load_posted_titles()
    posted_images = load_posted_images()
    posted_hashes = load_posted_hashes()
    print("URLs: " + str(len(posted_urls)) + " | Titles: " + str(len(posted_titles)) + " | Images: " + str(len(posted_images)) + " | Hashes: " + str(len(posted_hashes)))

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36'}

    MAX_POSTS_PER_RUN = 14
    posts_published = 0

    for category_label, feed_url in FEEDS.items():
        if posts_published >= MAX_POSTS_PER_RUN:
            print("Max " + str(MAX_POSTS_PER_RUN) + " posts reached. Stopping.")
            break

        print("\nChecking: " + category_label)

        try:
            feed_response = requests.get(feed_url, headers=headers, timeout=15)
            parsed_feed = feedparser.parse(feed_response.content)
        except Exception as e:
            print("Feed error: " + str(e))
            continue

        print("Found " + str(len(parsed_feed.entries)) + " articles")

        posted_from_this_feed = False

        for entry in parsed_feed.entries:
            if posted_from_this_feed:
                break
            if posts_published >= MAX_POSTS_PER_RUN:
                break

            news_link = entry.link
            news_title = entry.title

            if news_link in posted_urls:
                print("Skip URL: " + news_title[:50])
                continue

            normalized_title = normalize_title(news_title)
            if normalized_title in posted_titles:
                print("Skip Title: " + news_title[:50])
                continue

            raw_content = entry.content[0].value if hasattr(entry, 'content') and entry.content else entry.summary
            soup = BeautifulSoup(raw_content, 'html.parser')
            img_tag = soup.find('img')

            if not img_tag:
                try:
                    article_req = requests.get(news_link, headers=headers, timeout=10)
                    article_soup = BeautifulSoup(article_req.text, 'html.parser')
                    meta_img = article_soup.find('meta', property='og:image')
                    if meta_img and meta_img.get('content'):
                        img_url = meta_img['content']
                        img_tag = BeautifulSoup("<img src='" + img_url + "' alt='Nail Art Image' />", 'html.parser').img
                except:
                    pass

            if not img_tag:
                print("No Image: " + news_title[:50])
                continue

            img_src = img_tag.get('src', '')
            if img_src and img_src in posted_images:
                print("Skip Image: " + news_title[:50])
                continue

            clean_text = soup.get_text(separator="\n").strip()

            # Filter: Only post nail-related content
            if not is_nail_related(news_title, clean_text):
                print("Not nail related. Skip: " + news_title[:50])
                continue

            content_hash_value = content_hash(clean_text)
            if content_hash_value and content_hash_value in posted_hashes:
                print("Skip Content (duplicate): " + news_title[:50])
                continue

            print("AI Processing: " + news_title[:60])
            final_title, final_content = process_content_with_ai(news_title, clean_text)

            if not final_content:
                print("AI fail. Skip.")
                continue

            # Optimize first image
            img_tag = optimize_image_tag(img_tag, is_lcp=True)
            image_html = str(img_tag)

            final_html_content = (
                image_html
                + "<br><br><p>"
                + final_content
                + "</p><br><br><p><em>Source: "
                + category_label
                + "</em></p>"
            )

            final_label = LABEL_MAP.get(category_label, category_label)

            post_url = post_to_blogger(final_title, final_html_content, [final_label])

            if post_url:
                save_posted_url(news_link)
                save_posted_title(normalized_title)
                if img_src:
                    save_posted_image(img_src)
                save_posted_hash(content_hash_value)

                posted_urls.add(news_link)
                posted_titles.add(normalized_title)
                if img_src:
                    posted_images.add(img_src)
                posted_hashes.add(content_hash_value)

                posts_published += 1
                posted_from_this_feed = True

                print("Post " + str(posts_published) + "/" + str(MAX_POSTS_PER_RUN) + " published with label: " + final_label + " (from " + category_label + ")")
                print("=" * 50)

    print("\nTotal posts published this run: " + str(posts_published))

if __name__ == "__main__":
    fetch_and_post_news()
    print("Script Finished!")
