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
YOUR_BLOG_URL = os.environ.get("BLOG_URL", "https://nailovia.yourbolt.online")

# ==========================================
# FEEDS (Real Nail Art Blogs - Listicle Style)
# ==========================================
FEEDS = {
    "Nail Art Trends": "https://sonailicious.com/feed/",
    "Nail Design Ideas": "https://www.naildesigns.com/feed/",
    "Nail Art Gallery": "https://nailartgallery.com/feed/",
    "Nail Tutorials": "https://choosynails.com/feed/",
    "Nail Art Inspiration": "https://nailsblaze.com/feed/",
    "Beauty & Nails": "https://www.bangstyle.com/feed/",
    "Nail Trends 2026": "https://www.scratchmagazine.co.uk/feed/",
    "Simple Nail Designs": "https://www.themilliondollarmama.com/feed/",
    "Nail Care Tips": "https://www.organicauthority.com/tag/nail/feed",
    "Nail Art & Design": "https://www.nailsmag.com/feed/",
    "Pretty Nail Ideas": "https://mirelleinspo.com/feed/",
    "Nail Polish Trends": "https://pak.net.pk/tag/nail-art/feed/",
}

LABEL_MAP = {
    "Nail Art Trends": "Nail Art Trends",
    "Nail Design Ideas": "Nail Design Ideas",
    "Nail Art Gallery": "Nail Art Gallery",
    "Nail Tutorials": "Nail Tutorials",
    "Nail Art Inspiration": "Nail Art Inspiration",
    "Beauty & Nails": "Beauty & Nails",
    "Nail Trends 2026": "Nail Trends 2026",
    "Simple Nail Designs": "Simple Nail Designs",
    "Nail Care Tips": "Nail Care Tips",
    "Nail Art & Design": "Nail Art & Design",
    "Pretty Nail Ideas": "Pretty Nail Ideas",
    "Nail Polish Trends": "Nail Polish Trends",
}

POSTED_URLS_FILE = "posted_urls.txt"
POSTED_TITLES_FILE = "posted_titles.txt"
POSTED_IMAGES_FILE = "posted_images.txt"
POSTED_HASHES_FILE = "posted_hashes.txt"

NAIL_KEYWORDS = [
    "nail", "nails", "manicure", "pedicure", "polish", "gel",
    "acrylic", "lacquer", "cuticle", "nail art", "nail design",
    "nail idea", "nail trend", "nail inspo", "nail tutorial"
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
    snippet = re.sub(r'\s+', '', text[:300]).strip().lower()
    return hashlib.md5(snippet.encode('utf-8')).hexdigest()

def has_english_letters(text):
    if not text:
        return False
    return bool(re.search(r'[A-Za-z]', text))

def has_non_english_script(text):
    if not text:
        return True
    bad_ranges = [
        (0x0600, 0x06FF), (0x0750, 0x077F), (0x0900, 0x097F),
        (0x0980, 0x09FF), (0x0A00, 0x0A7F), (0x0A80, 0x0AFF),
        (0x0B00, 0x0B7F), (0x0B80, 0x0BFF), (0x0C00, 0x0C7F),
        (0x0C80, 0x0CFF), (0x0D00, 0x0D7F), (0x0D80, 0x0DFF),
        (0x0E00, 0x0E7F), (0x0E80, 0x0EFF), (0x4E00, 0x9FFF),
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
# FULL ARTICLE SCRAPER (NEW - Main Update)
# ==========================================

def scrape_full_article(url, headers):
    """
    RSS link pe ja kar poori article scrape karta hai.
    Returns: (full_text, list_of_image_urls)
    """
    try:
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Scripts and styles remove karein
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'iframe']):
            tag.decompose()

        # Main article body dhoondein
        article_body = None
        selectors = [
            'article',
            'div.entry-content',
            'div.post-content',
            'div.article-content',
            'div.blog-post-content',
            'div.content-area',
            'main',
        ]
        for sel in selectors:
            article_body = soup.select_one(sel)
            if article_body:
                break

        if not article_body:
            article_body = soup.body if soup.body else soup

        # Saari images nikaalein
        images = []
        for img in article_body.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if not src or not src.startswith('http'):
                continue
            # Skip small icons, avatars, ads
            if any(skip in src.lower() for skip in ['avatar', 'icon', 'logo', 'ad-', 'ads.', '1x1', 'pixel', 'gravatar']):
                continue
            if src not in images:
                images.append(src)
                if len(images) >= 40:
                    break

        # Fallback: og:image
        if not images:
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'):
                images.append(og_img['content'])

        # Saara text nikaalein
        paragraphs = article_body.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li'])
        text_parts = []
        for p in paragraphs:
            t = p.get_text(strip=True)
            if len(t) > 25:
                text_parts.append(t)

        full_text = "\n\n".join(text_parts)

        # Text limit (AI token limit ke liye)
        if len(full_text) > 8000:
            full_text = full_text[:8000]

        print("Scraped: " + str(len(images)) + " images | " + str(len(full_text)) + " chars")
        return full_text, images

    except Exception as e:
        print("Scrape error: " + str(e))
        return "", []

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
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.4,
                        "maxOutputTokens": 8192
                    }
                }
                response = requests.post(url, headers=headers, json=data, timeout=60)
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
                    "content": "You are a professional English blog writer specializing in nail art. You ONLY output the final result in the exact requested format. You NEVER explain, reason, or use placeholders."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4,
            "max_tokens": 6000
        }
        response = requests.post(url, headers=headers, json=data, timeout=60)
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
            "X-Title": "Nailovia Blog"
        }
        data = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional English blog writer specializing in nail art. You ONLY output the final result in the exact requested format. You NEVER explain, reason, or use placeholders."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4,
            "max_tokens": 6000
        }
        response = requests.post(url, headers=headers, json=data, timeout=60)
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
# PROMPT BUILDER (Listicle Style - HTML Output)
# ==========================================

def build_prompt(source_title, original_content, image_count, strict_mode=False):
    prompt = "TASK: Write a comprehensive, long-form, SEO-optimized listicle blog post in ENGLISH based on the source content below.\n\n"
    prompt += "SOURCE TITLE: " + source_title + "\n\n"
    prompt += "SOURCE CONTENT:\n" + original_content + "\n\n"
    prompt += "SOURCE HAS " + str(image_count) + " IMAGES AVAILABLE.\n\n"

    prompt += "STRICT RULES:\n"
    prompt += "- Output ONLY the final result in HTML. No thinking, no reasoning, no explanation.\n"
    prompt += "- The article MUST be a listicle (numbered list of designs/ideas).\n"
    prompt += "- Minimum 10 items in the list, maximum 25 items.\n"
    prompt += "- EACH item MUST have:\n"
    prompt += "  * An <h3> subheading with the design name\n"
    prompt += "  * A detailed paragraph (3-5 sentences) describing the design\n"
    prompt += "  * A 'How to recreate' section with step-by-step tips\n"
    prompt += "- Insert <img> placeholder tags like <img data-img='1'>, <img data-img='2'> after each item's H3. We will replace them with real images.\n"
    prompt += "- Use proper HTML tags: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>.\n"
    prompt += "- Do NOT use placeholders like [Title Here]. Write real content.\n"
    prompt += "- Output MUST be 100% English. No other scripts.\n"
    prompt += "- Make it engaging, friendly, and informative for a nail art audience.\n"
    prompt += "- Include a short intro paragraph and a conclusion.\n\n"

    if strict_mode:
        prompt += "!!!!! WARNING !!!!!\n"
        prompt += "Your previous response was rejected. Output ONLY the final English HTML listicle in the exact format below.\n\n"

    prompt += "OUTPUT FORMAT (follow exactly, nothing else):\n"
    prompt += "TITLE: <SEO optimized title with year 2026>\n"
    prompt += "CONTENT: <full HTML article here>\n"
    return prompt

# ==========================================
# AI PROCESSING FUNCTION
# ==========================================

def parse_ai_response(response):
    if not response:
        return None, None

    response_lower = response.lower()
    garbage_signs = [
        "we need to", "let's see", "let me", "wait,", "actually we must",
        "[title here]", "[content here]", "[english title here]",
        "task:", "input title:", "rules:", "output format:",
        "here is the", "here's the", "i cannot", "i can't",
    ]
    for sign in garbage_signs:
        if sign in response_lower:
            print("Garbage detected: " + sign)
            return None, None

    try:
        if "TITLE:" in response and "CONTENT:" in response:
            parts = response.split("CONTENT:", 1)
            title_part = parts[0].replace("TITLE:", "").strip()
            content_part = parts[1].strip()
            title_part = title_part.replace("TITLE:", "").strip()
            return (title_part if title_part else None, content_part if content_part else None)
        else:
            print("AI format invalid (missing TITLE/CONTENT)")
            return None, None
    except Exception as e:
        print("Parse error: " + str(e))
        return None, None

def process_content_with_ai(source_title, original_content, image_count):
    final_title = source_title
    final_content = None
    last_response = None

    for attempt in range(3):
        print("AI Attempt " + str(attempt + 1) + "/3")
        strict = (attempt > 0)
        prompt = build_prompt(source_title, original_content, image_count, strict_mode=strict)
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

        # Check for bad scripts (non-English)
        if has_non_english_script(temp_title) or has_non_english_script(temp_content):
            print("Non-English script detected. Retrying...")
            time.sleep(2)
            continue

        if not has_english_letters(temp_content) or len(temp_content) < 500:
            print("Content too short or not English. Retrying...")
            time.sleep(2)
            continue

        final_title = temp_title
        final_content = temp_content
        print("English listicle content valid. Length: " + str(len(final_content)))
        break

    if not final_content and last_response:
        print("3 attempts failed. Using last response anyway.")
        final_title, final_content = parse_ai_response(last_response)

    if not final_content:
        print("AI completely failed.")
        return None, None

    if not final_title:
        final_title = source_title

    return final_title, final_content

# ==========================================
# IMAGE INJECTION (Insert Images into HTML)
# ==========================================

def inject_images_into_html(html_content, image_urls):
    """
    AI ke <img data-img='N'> placeholders ko real images se replace karta hai.
    """
    if not image_urls:
        return html_content

    used = set()
    counter = [0]

    def replacer(match):
        idx = int(match.group(1)) - 1
        if idx < 0 or idx >= len(image_urls):
            # Fallback: use next available image
            while counter[0] < len(image_urls) and counter[0] in used:
                counter[0] += 1
            if counter[0] >= len(image_urls):
                return ""
            idx = counter[0]
        used.add(idx)
        url = image_urls[idx]
        counter[0] = idx + 1
        return (
            '<img src="' + url + '" alt="Nail Art Design" '
            'loading="lazy" decoding="async" width="800" height="450" '
            'referrerpolicy="no-referrer" style="max-width:100%; height:auto; margin:12px 0; border-radius:8px;">'
        )

    # Pattern: <img data-img='N'> or <img data-img="N">
    html_content = re.sub(r"<img[^>]*data-img=['\"](\d+)['\"][^>]*>", replacer, html_content)

    # Agar koi placeholder nahi tha, to har 500 chars pe image insert karein
    if not re.search(r'<img\s+src=', html_content, re.I):
        print("No placeholders found. Injecting images manually...")
        paragraphs = html_content.split('</h3>')
        new_parts = []
        img_idx = 0
        for i, part in enumerate(paragraphs):
            new_parts.append(part)
            if i < len(paragraphs) - 1 and img_idx < len(image_urls):
                new_parts.append(
                    '</h3><img src="' + image_urls[img_idx] + '" alt="Nail Art Design" '
                    'loading="lazy" decoding="async" width="800" height="450" '
                    'referrerpolicy="no-referrer" style="max-width:100%; height:auto; margin:12px 0; border-radius:8px;">'
                )
                img_idx += 1
        html_content = ''.join(new_parts)

    return html_content

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

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}

    MAX_POSTS_PER_RUN = 6
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

            # === STEP 1: Full article scrape ===
            print("Scraping full article: " + news_title[:50])
            full_text, all_images = scrape_full_article(news_link, headers)

            if not full_text or len(full_text) < 400:
                print("Article too short. Skip.")
                continue

            if not all_images or len(all_images) < 3:
                print("Not enough images (" + str(len(all_images)) + "). Skip.")
                continue

            # === STEP 2: Nail-related filter ===
            if not is_nail_related(news_title, full_text):
                print("Not nail related. Skip: " + news_title[:50])
                continue

            # === STEP 3: Duplicate content check ===
            content_hash_value = content_hash(full_text)
            if content_hash_value and content_hash_value in posted_hashes:
                print("Duplicate content. Skip: " + news_title[:50])
                continue

            # === STEP 4: AI processing ===
            print("AI Processing: " + news_title[:60] + " | Images: " + str(len(all_images)))
            urdu_title, ai_content = process_content_with_ai(news_title, full_text, len(all_images))

            if not ai_content:
                print("AI fail. Skip.")
                continue

            # === STEP 5: Inject real images into HTML ===
            final_content_html = inject_images_into_html(ai_content, all_images)

            # Add source credit
            final_content_html += (
                '<br><br><p><em>Source: ' + category_label +
                ' | Original: <a href="' + news_link + '" rel="nofollow">' +
                news_title + '</a></em></p>'
            )

            # === STEP 6: Publish to Blogger ===
            final_label = LABEL_MAP.get(category_label, category_label)
            post_url = post_to_blogger(urdu_title, final_content_html, [final_label])

            if post_url:
                save_posted_url(news_link)
                save_posted_title(normalized_title)
                save_posted_hash(content_hash_value)
                for img in all_images[:5]:
                    save_posted_image(img)

                posted_urls.add(news_link)
                posted_titles.add(normalized_title)
                posted_hashes.add(content_hash_value)

                posts_published += 1
                posted_from_this_feed = True

                print("Post " + str(posts_published) + "/" + str(MAX_POSTS_PER_RUN) + " published! Label: " + final_label)
                print("=" * 50)

    print("\nTotal posts published this run: " + str(posts_published))

if __name__ == "__main__":
    fetch_and_post_news()
    print("Script Finished!")
