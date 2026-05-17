from fastapi import FastAPI, Request
from app.vectorizer import embed_text
from utils.data_loader import classify_sentence
from app.topic_extractor import extract_keywords
from sklearn.metrics.pairwise import cosine_similarity
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from urllib.parse import urlparse, unquote
import time
import base64
import re
import datetime
from typing import List
import requests
from fastapi.middleware.cors import CORSMiddleware
from googleapiclient.discovery import build
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
import os
import mysql.connector
from auth import router as auth_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sync-mind.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware, 
    secret_key="922005", 
    https_only=False,
    # On localhost, SameSite=None cookies are often rejected unless Secure=true.
    # Lax works for this app's same-site localhost flow and keeps session persistence stable.
    same_site="lax",
    max_age=3600,  
    path="/"
)

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


from migrations import run_migrations


@app.on_event("startup")
def _on_startup() -> None:
    run_migrations()

def get_db():
    return mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    port=int(os.getenv("DB_PORT"))
    ) 


app.include_router(auth_router, prefix="/auth")
def get_github(query: str, token: str | None = None):
    """Search public GitHub repositories.

    Token strategy (first non-empty wins):
      1. ``token`` argument — the user's OAuth access token from this
         session, when the caller has one. Highest rate limit and never
         expires while the user is connected.
      2. ``GITHUB_TOKEN`` env var — a static PAT, useful for
         server-side calls without an authenticated user.
      3. No auth — falls back to the public 60-req/hour limit, which
         is fine for occasional dashboard refreshes.

    The previous version hard-coded the env PAT and 401'd silently
    once the PAT expired, leaving the user with an empty
    recommendations list even though their OAuth token was valid.
    """
    candidates = [t for t in (token, GITHUB_TOKEN) if t]
    base_headers = {"Accept": "application/vnd.github+json"}
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": 15}
    url = "https://api.github.com/search/repositories"

    # Try each candidate token; on auth failure, drop it and retry. Final
    # attempt is unauthenticated.
    attempts: list[dict] = [
        {**base_headers, "Authorization": f"Bearer {c}"} for c in candidates
    ]
    attempts.append(base_headers)

    last_error: str | None = None
    for headers in attempts:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
        except Exception as e:
            last_error = f"request failed: {e}"
            continue

        if response.status_code == 200:
            data = response.json()
            repos = []
            for item in data.get("items", []):
                if not isinstance(item, dict):
                    continue
                owner = item.get("owner") or {}
                repos.append({
                    # GitHub search returns `name` and `full_name`. Use
                    # `full_name` ("owner/repo") so the cards remain
                    # disambiguated. Older callers / DB columns rely on
                    # the "title" key.
                    "title": item.get("full_name") or item.get("name") or "",
                    "url": item.get("html_url", ""),
                    "description": item.get("description", "") or "",
                    "stars": item.get("stargazers_count", 0),
                    "forks": item.get("forks_count", 0),
                    "language": item.get("language") or "Unknown",
                    "owner": owner.get("login", ""),
                })
            return repos

        # 401/403 → the token is bad / rate-limited; try the next option.
        last_error = f"{response.status_code} {response.text[:200]}"
        if response.status_code not in (401, 403):
            print("GitHub API Error:", last_error)
            return []
        print(f"GitHub auth failed ({response.status_code}); falling back.")

    print(f"Error in get_github: all attempts failed; last error: {last_error}")
    return []


from googleapiclient.discovery import build
from datetime import datetime, timezone
import isodate

def get_yt(query: str):
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY)

        # Step 1: Search videos
        search_request = youtube.search().list(
            q=query,
            part='snippet',
            type='video',
            maxResults=25
        )
        search_response = search_request.execute()

        video_ids = [item['id']['videoId'] for item in search_response['items']]
        if not video_ids:
            return []

        # Step 2: Get video metadata
        video_request = youtube.videos().list(
            part="contentDetails,statistics,snippet",
            id=",".join(video_ids)
        )
        video_response = video_request.execute()
        result = []

        for item in video_response['items']:
            title = item['snippet']['title']
            description = item['snippet']['description']
            channel = item['snippet']['channelTitle']
            published_at = item['snippet']['publishedAt']
            duration = isodate.parse_duration(item['contentDetails']['duration']).total_seconds()
            views = int(item['statistics'].get('viewCount', 0))

            # Convert published date to "how old" format
            published_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            age_days = (datetime.now(timezone.utc) - published_time).days

            video_data = {
                "title": title,
                "description": description,
                "url": f"https://www.youtube.com/watch?v={item['id']}",
                "channel": channel,
                "published_at": published_time.isoformat(),
                "duration_seconds": duration,
                "views": views,
                "age_days": age_days
            }
            result.append(video_data)

        return result

    except Exception as e:
        print(f"Error in get_yt: {e}")
        return []


def get_courses(query: str):
    try:
        chrome_options = Options()#used to choose how browser behaves when launched by selenium
        chrome_options.add_argument("--headless=new")#This runs Chrome in headless mode, meaning without opening a visible browser window.
        chrome_options.add_argument("--disable-gpu")#Disables GPU acceleration.
        chrome_options.add_argument("--log-level=3")#Reduces the amount of logging output from Chrome.
        driver = webdriver.Chrome(options=chrome_options)

        url = f"https://www.coursera.org/search?query={query.replace(' ', '%20')}"
        driver.get(url)
        time.sleep(5)

        # Get all list items (course cards)
        course_cards = driver.find_elements(By.TAG_NAME, "li")

        seen_links = set()
        response = []

        for card in course_cards:
            try:
                a_tag = card.find_element(By.TAG_NAME, "a")
                href = a_tag.get_attribute("href")

                if not href or "/learn/" not in href or href in seen_links:
                    continue
                seen_links.add(href)

                title_elem = a_tag.find_element(By.TAG_NAME, "h3")
                title = title_elem.text.strip()

                provider_elem = card.find_element(By.CLASS_NAME, "cds-ProductCard-partnerNames")
                provider = provider_elem.text.strip()
                star_elem_div = card.find_element(By.CLASS_NAME,"cds-RatingStat-sizeLabel")
                star_elem = star_elem_div.find_element(By.TAG_NAME,"span")
                star = star_elem.text.strip()

                ppl_elem = star_elem_div.find_element(By.CSS_SELECTOR,"div.css-vac8rf")
                ppl = ppl_elem.text.strip()

                info_elem_div = card.find_element(By.CLASS_NAME,"cds-CommonCard-metadata")
                info = info_elem_div.find_element(By.TAG_NAME,"p").text.strip()

                if title:
                    response.append({
                        "title": title,
                        "url": href,
                        "provider": provider,
                        "star":star,
                        "ppl":ppl,
                        "info":info
                    })

            except Exception:
                continue

        driver.quit()
        return response

    except Exception as e:
        print(f"Error in get_courses: {e}")
        return []
    
def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)  # Remove excessive whitespace
    text = re.sub(r'<.*?>', '', text)  # Remove HTML
    text = re.sub(r'[^\w\s]', '', text)  # Remove special characters
    return text.strip()

def should_update_youtube(user_id: int) -> bool:
    db = get_db()
    db.execute("SELECT last_updated FROM youtube_user_data WHERE user_id = %s", (user_id,))
    row = db.fetchone()
    if not row:
        return True  # No data yet
    return (datetime.now() - row[0]).days > 6

from datetime import datetime
import requests
import mysql.connector
from fastapi import Request
from typing import List

@app.post("/fetch")
def fetch_youtube_behavior(access_token: str, request: Request) -> List[str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    collected = set()
    recent_liked_title = None

    def get_items(url, params=None):
        try:
            res = requests.get(url, headers=headers, params=params)
            if res.status_code == 200:
                return res.json().get("items", [])
            else:
                print("Error:", res.status_code, res.text)
                return []
        except Exception as e:
            print("Request failed:", e)
            return []

    def extract_from_snippet(snippet):
        title = snippet.get("title", "")
        desc = snippet.get("description", "")
        text = clean_text(f"{title} {desc}")
        return text if len(text.split()) > 3 else None

    liked = get_items("https://www.googleapis.com/youtube/v3/videos", {
        "part": "snippet",
        "myRating": "like",
        "maxResults": 20
    })
    for idx, item in enumerate(liked):
        snippet = item.get("snippet", {})
        text = extract_from_snippet(snippet)
        if text:
            collected.add(text)
        if idx == 0:
            recent_liked_title = snippet.get("title", None)

    subs = get_items("https://www.googleapis.com/youtube/v3/subscriptions", {
        "part": "snippet",
        "mine": "true",
        "maxResults": 50
    })
    for sub in subs:
        text = extract_from_snippet(sub.get("snippet", {}))
        if text:
            collected.add(text)

    watch_later = get_items("https://www.googleapis.com/youtube/v3/playlistItems", {
        "part": "snippet",
        "playlistId": "WL",
        "maxResults": 50
    })
    for item in watch_later:
        text = extract_from_snippet(item.get("snippet", {}))
        if text:
            collected.add(text)

    try:
        channel_info = get_items("https://www.googleapis.com/youtube/v3/channels", {
            "part": "snippet,statistics",
            "mine": "true"
        })
        if not channel_info:
            raise Exception("No channel info found.")
        channel = channel_info[0]
        channel_name = channel["snippet"]["title"]
        subscribers = int(channel["statistics"].get("subscriberCount", 0))
    except Exception as e:
        print("Channel info error:", e)
        channel_name = "Unknown"
        subscribers = 0

    try:
        time_spent = int(request.headers.get("X-Time-Spent", "0"))
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user_id FROM user_tokens WHERE access_token = %s", (access_token,))
        user_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO youtube_user_data (user_id, channel_name, subscribers, time_spent, recent_liked_video, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                channel_name = VALUES(channel_name),
                subscribers = VALUES(subscribers),
                time_spent = VALUES(time_spent),
                recent_liked_video = VALUES(recent_liked_video),
                last_updated = VALUES(last_updated)
        """, (
            user_id,
            channel_name,
            subscribers,
            time_spent,
            recent_liked_title,
            datetime.now()
        ))
        db.commit()

    except Exception as e:
        print("DB Error:", e)

    return list(collected)


def fetch_readme_snippet(owner, repo_name, headers, lines=5):
    readme_url = f"https://api.github.com/repos/{owner}/{repo_name}/readme"
    readme_res = requests.get(readme_url, headers=headers)
    if readme_res.status_code != 200:
        return ""

    content = readme_res.json().get("content")
    if not content:
        return ""

    try:
        decoded = base64.b64decode(content).decode("utf-8")
        return "\n".join(decoded.splitlines()[:lines])
    except Exception:
        return ""
    
@app.get("/get_userid")
def get_user_id(email: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT id
        FROM users
        WHERE email = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (email, ))
    
    result = cursor.fetchone()
    
    if not result:
        return {"error": "Token not found"}

    return result[0]

    
def get_access_token(user_id: int, platform: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT access_token
        FROM user_tokens
        WHERE user_id = %s AND platform = %s
        ORDER BY updated_at DESC
        LIMIT 1
    """, (user_id, platform))
    
    result = cursor.fetchone()
    
    if not result:
        return None

    return result[0]

@app.get("/token")
def get_token(user_id: int, platform: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT access_token
        FROM user_tokens
        WHERE user_id = %s AND platform = %s
        ORDER BY updated_at DESC
        LIMIT 1
    """, (user_id, platform))
    
    result = cursor.fetchone()
    
    if not result:
        return None

    return result[0]

@app.post("/fetch_git")
def fetch_github_behaviour(access_token: str):
    headers = {"Authorization": f"Bearer {access_token}"}

    def safe_get_json(url, params=None):
        try:
            res = requests.get(url, headers=headers, params=params)
            if res.status_code == 200:
                return res.json()
            else:
                print(f"GitHub API Error {url}: {res.status_code} {res.text}")
                return None
        except Exception as e:
            print(f"Request failed for {url}:", e)
            return None

    # Fetch user info
    user_info = safe_get_json("https://api.github.com/user")
    if not isinstance(user_info, dict):
        return {"error": "Failed to fetch GitHub user info"}

    username = user_info.get("login", "")
    total_repos = user_info.get("public_repos", 0)

    # Fetch contributions
    events = safe_get_json(f"https://api.github.com/users/{username}/events/public")
    contributions = 0
    if isinstance(events, list):
        contributions = sum(1 for e in events if e.get("type") in ["PushEvent", "PullRequestEvent", "IssuesEvent"])
    else:
        print("Events data not a list:", events)

    # Starred repos
    starred = safe_get_json("https://api.github.com/user/starred") or []
    total_stars = sum(repo.get("stargazers_count", 0) for repo in starred if isinstance(repo, dict))

    history = []

    # History from starred
    for repo in starred:
        if not isinstance(repo, dict):
            continue
        owner = repo.get("owner", {}).get("login", "")
        name = repo.get("name", "")
        desc = repo.get("description", "")
        readme = fetch_readme_snippet(owner, name, headers)
        history.append(f"{name} {desc} {readme}".strip())

    # User repos
    repos = safe_get_json("https://api.github.com/user/repos") or []
    for repo in repos:
        if not isinstance(repo, dict):
            continue
        name = repo.get("name", "")
        desc = repo.get("description", "")
        readme = fetch_readme_snippet(username, name, headers)
        history.append(f"{name} {desc} {readme}".strip())

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user_id FROM user_tokens WHERE access_token = %s", (access_token,))
        user_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO github_user_data (user_id, public_repos, total_stars, contributions, last_updated)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                public_repos = VALUES(public_repos),
                total_stars = VALUES(total_stars),
                contributions = VALUES(contributions),
                last_updated = VALUES(last_updated)
        """, (user_id, total_repos, total_stars, contributions, datetime.now()))
        db.commit()
    except Exception as e:
        print("DB Error (GitHub):", e)

    return {"history": [line for line in history if line]}


import time

@app.get("/get_github_data")
def get_github_data(email: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user_row = cursor.fetchone()
    if not user_row:
        return {"error": "User not found"}
    user_id = user_row[0]

    access_token = get_access_token(user_id=user_id, platform="github")

    try:
        response = requests.post("http://localhost:8000/fetch_git", params={"access_token": access_token})
        history = response.json().get("history", [])
        if response.status_code != 200:
            print("Fetch GitHub failed:", response.text)

        # Optional: Wait a short moment to ensure DB commit is done
        time.sleep(0.5)

        # OR re-open DB connection for fresher state
        db = get_db()
        cursor = db.cursor()

        requests.post(f"http://localhost:8000/recommend-git/?token={access_token}", json={"history": history})
    except Exception as e:
        print("Failed to fetch GitHub data internally:", e)

    cursor.execute("""
        SELECT public_repos, total_stars, contributions, last_updated
        FROM github_user_data
        WHERE user_id = %s
    """, (user_id,))
    data = cursor.fetchone()

    if not data:
        return {"error": "No GitHub data found for this user"}

    return {
        "repos": data[0],
        "stars": data[1],
        "contributions": data[2],
        "lastUpdated": data[3].isoformat() if data[3] else None,
    }


import time

@app.get("/get_youtube_data")
def get_youtube_data(email: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user_row = cursor.fetchone()

    if not user_row:
        return {"error": "User not found"}

    user_id = user_row[0]

    access_token = get_access_token(user_id=user_id, platform="google")

    try:
        response = requests.post("http://localhost:8000/fetch", params={"access_token": access_token})
        history = response.json()
        if response.status_code != 200:
            print("Fetch YouTube failed:", response.text)

        # Wait briefly to ensure DB write finishes
        time.sleep(0.5)

        # Reopen DB connection to ensure we get fresh data
        db = get_db()
        cursor = db.cursor()

        requests.post(f"http://localhost:8000/recommend-yt/?token={access_token}", json={
            "history": history
        })
    except Exception as e:
        print("Failed to fetch YouTube data internally:", e)

    cursor.execute("""
        SELECT channel_name, subscribers, recent_liked_video, last_updated
        FROM youtube_user_data
        WHERE user_id = %s
    """, (user_id,))
    data = cursor.fetchone()

    if not data:
        return {"error": "No YouTube data found for this user"}

    return {
        "channelName": data[0],
        "subscribers": data[1],
        "recentLikedVideo": data[2],
        "lastUpdated": data[3].isoformat() if data[3] else None
    }


class UserHistory(BaseModel):
    history: list[str]

from datetime import datetime
@app.get("/auth/status")
def auth_status(request: Request):
   
    google_user = request.session.get("google_user")
    google_user = request.session.get("google_user")
    github_user = request.session.get("github_user")

    return {
        "authenticated": bool(google_user or github_user),
        "google_connected": bool(google_user),
        "github_connected": bool(github_user),
        "google_email": google_user.get("email") if google_user else None,
        "google_name": google_user.get("name") if google_user else None,
        "github_email": github_user.get("email") if github_user else None
    }


@app.post("/recommend-yt")
def recommendYT(data: UserHistory, token: str):
    cleaned_history = []
    for item in data.history:
        item = item.replace("#", "").replace("*", "").replace("None", "").strip()
        if len(item) > 5:
            cleaned_history.append(item)

    if not cleaned_history:
        return {
            "source": "youtube",
            "keywords": [],
            "recommendations": [],
            "message": "We couldn't detect much from your recent activity. Try engaging with more content first."
        }

    user_keywords = extract_keywords(cleaned_history)
    # Classify each keyphrase as a whole — splitting "machine learning" into
    # "machine" + "learning" was destroying the very context KeyBERT extracted.
    filtered_keywords = [kp for kp in user_keywords if classify_sentence(kp) == 1]
    filtered_keywords = list(dict.fromkeys(filtered_keywords))
    print("filtered keywords: ", filtered_keywords)
    if not filtered_keywords:
        # Defensive fallback if the KB threshold rejected everything.
        filtered_keywords = list(dict.fromkeys(user_keywords))
        if not filtered_keywords:
            return {
                "source": "youtube",
                "keywords": [],
                "recommendations": [],
                "message": "Most of your recent activity is non-educational. Try watching more educational content."
            }


    try:
        user_vector = embed_text(" ".join(filtered_keywords)).reshape(1, -1)
    except Exception as e:
        return {
            "source": "youtube",
            "error": f"Failed to embed user keywords: {str(e)}"
        }

    resources = get_yt(" ".join(filtered_keywords))
    if not resources:
        return {
            "source": "youtube",
            "keywords": user_keywords,
            "recommendations": [],
            "message": "No related videos found on YouTube. Try expanding your topics."
        }

    resource_text = [r['title'] + " " + r['description'] for r in resources]
    try:
        resource_vector = embed_text(resource_text)
    except Exception as e:
        return {
            "source": "youtube",
            "keywords": filtered_keywords,
            "recommendations": [],
            "message": f"Failed to embed YouTube content: {e}"
        }

    try:
        similarities = cosine_similarity(user_vector, resource_vector)[0]
        top_indexes = similarities.argsort()[::-1][:10]
        recommended_videos = [resources[i] for i in top_indexes]
    except Exception as e:
        return {
            "source": "youtube",
            "keywords": filtered_keywords,
            "recommendations": [],
            "message": f"Similarity computation failed: {e}"
        }

    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT user_id FROM user_tokens WHERE access_token = %s", (token,))
        result = cursor.fetchone()
        if result is None:
            raise Exception("Invalid token: user not found.")
        user_id = result[0]

        cursor.execute("DELETE FROM youtube_recommendations WHERE user_id = %s", (user_id,))

        for video in recommended_videos:
            cursor.execute("""
                INSERT INTO youtube_recommendations 
                (user_id, title, description, published_at, duration, views, channel_name,url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                video['title'],
                video['description'],
                video['published_at'],
                str(video['duration_seconds']) + " seconds", 
                video['views'],
                video['channel'],
                video["url"]
            ))

        db.commit()
    except Exception as e:
        print("DB Error (YouTube recommendation insert):", e)

    return {
        "message":"recommendations stored"
    }

@app.get("/get_github_recommendations")
def get_github_recommendations(email: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user_row = cursor.fetchone()
    if not user_row:
        return {"error": "User not found"}
    user_id = user_row[0]

    cursor.execute("""
        SELECT repo_name, url, description, stars, forks, language, owner
        FROM github_recommendations
        WHERE user_id = %s
        ORDER BY stars DESC
        LIMIT 10
    """, (user_id,))
    rows = cursor.fetchall()

    return [
        {
            "repoName": row[0],
            "url": row[1],
            "description": row[2],
            "stars": row[3],
            "forks": row[4],
            "language": row[5],
            "owner": row[6]
        }
        for row in rows
    ]

@app.get("/get_coursera_recommendations")
def get_coursera_recommendations(email: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user_row = cursor.fetchone()
    if not user_row:
        return {"error": "User not found"}
    user_id = user_row[0]

    cursor.execute("""
        SELECT course_title, provider, enrolled, rating, fetched_at, url, info
        FROM coursera_recommendations
        WHERE user_id = %s
        ORDER BY rating DESC
        LIMIT 10
    """, (user_id,))
    rows = cursor.fetchall()

    return [
        {
            "title": row[0],
            "provider": row[1],
            "enrolled": row[2],
            "rating": row[3],
            "fetchedAt": row[4].isoformat() if row[4] else None,
            "url": row[5],
            "info": row[6]
        }
        for row in rows
    ]

@app.get("/get_youtube_recommendations")
def get_youtube_recommendations(email: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user_row = cursor.fetchone()
    if not user_row:
        return {"error": "User not found"}
    user_id = user_row[0]

    cursor.execute("""
        SELECT title, description, published_at, duration, views, channel_name, url
        FROM youtube_recommendations
        WHERE user_id = %s
        ORDER BY views DESC
        LIMIT 10
    """, (user_id,))
    rows = cursor.fetchall()

    recommendations = [
        {
            "title": row[0],
            "description": row[1],
            "publishedAt": row[2].isoformat() if row[2] else None,
            "duration": row[3],
            "views": row[4],
            "channelName": row[5],
            "url": row[6]
        }
        for row in rows
    ]

    return recommendations



@app.post("/recommend-git")
def recommendGIT(data: UserHistory,token: str):
    cleaned_history = []
    for item in data.history:
        item = item.replace("#", "").replace("*", "").replace("None", "").strip()
        if len(item) > 5:
            cleaned_history.append(item)

    full_text = " ".join(cleaned_history)

    user_keywords = extract_keywords([full_text])
    if not user_keywords:
        return {
            "source": "github",
            "keywords": [],
            "recommendations": [],
            "message": "We couldn't extract meaningful content from your GitHub activity. Try starring or working on more tech-related repositories."
        }

    try:
        user_vector = embed_text(" ".join(user_keywords))
    except Exception as e:
        return {"error": f"Embedding user keywords failed: {e}"}
    # Use the user's OAuth token for the repo search so we don't depend
    # on the stale server-side PAT (which has been 401'ing).
    resources = get_github(" ".join(user_keywords), token=token)
    if not resources:
        return {
            "source": "github",
            "keywords": user_keywords,
            "recommendations": [],
            "message": "No GitHub repositories found matching your interests."
        }

    resource_text = [r['title'] + " " + r['description'] for r in resources]

    try:
        resource_vector = embed_text(resource_text)
    except Exception as e:
        return {"error": f"Embedding resources failed: {e}"}

    try:
        similarities = cosine_similarity(user_vector, resource_vector)[0]
        top_indexes = similarities.argsort()[::-1][:10]
        recommended_titles = [resources[i] for i in top_indexes]
    except Exception as e:
        return {"error": f"Similarity computation failed: {e}"}

    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT user_id FROM user_tokens WHERE platform = %s AND access_token = %s
        """, ("github", token))  
        user_id_row = cursor.fetchone()
        if not user_id_row:
            return {"error": "User not found for the given token."}
        user_id = user_id_row[0]

        cursor.execute("DELETE FROM github_recommendations WHERE user_id = %s", (user_id,))

        for repo in recommended_titles:
            cursor.execute("""
                INSERT INTO github_recommendations 
                (user_id, repo_name, url, description, stars, forks, language, owner)
                VALUES (%s, %s, %s, %s, %s, %s, %s,%s)
            """, (
                user_id,
                repo["title"],
                repo["url"],
                repo["description"],
                repo["stars"],
                repo["forks"],
                repo["language"],
                repo["owner"]
            ))
        print("db stored")
        db.commit()
    except Exception as e:
        return {"error": f"DB storage failed: {e}"}

    return {
        "source": "github",
        "keywords": user_keywords,
        "scores": similarities[top_indexes].tolist(),
        "recommendations": recommended_titles
    }

@app.post("/recommend-coursera")
def recommendCOURSERA(data: UserHistory, email:str):
    course_titles = []
    print(f"[Coursera Recommend] Incoming history items: {len(data.history)}")
    for item in data.history:
        raw_item = (item or "").strip()
        if not raw_item:
            continue
        try:
            parsed = urlparse(raw_item)
            path = unquote((parsed.path or "").strip("/"))
            parts = [p for p in path.split("/") if p]

            # Accept both URLs and plain keyword/title strings.
            if parts:
                candidate = parts[-1]
            else:
                candidate = raw_item

            normalized = unquote(candidate).replace("-", " ").replace("_", " ").strip()
            if len(normalized) > 2:
                course_titles.append(normalized)
        except Exception:
            continue

    course_titles = list(dict.fromkeys(course_titles))
    print(f"[Coursera Recommend] Parsed titles/keywords: {course_titles[:10]}")

    user_keywords: list[str] = []
    if course_titles:
        user_keywords = extract_keywords([" ".join(course_titles)]) or course_titles[:10]

    # Cross-platform fallback: if the Coursera extractor didn't surface
    # anything useful (very common — depends on the user being logged in
    # on coursera.org), reuse the keywords we already learned from their
    # GitHub and YouTube activity. That way "connect Coursera" still
    # produces relevant courses end-to-end.
    if not user_keywords:
        try:
            db_lookup = get_db()
            cur = db_lookup.cursor()
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
            if row:
                uid = row[0]
                chunks: list[str] = []
                cur.execute(
                    "SELECT repo_name, description, language FROM github_recommendations WHERE user_id = %s LIMIT 20",
                    (uid,),
                )
                for repo_name, desc, lang in cur.fetchall():
                    chunks.append(" ".join(x for x in (repo_name, desc, lang) if x))
                cur.execute(
                    "SELECT title, channel_name FROM youtube_recommendations WHERE user_id = %s LIMIT 20",
                    (uid,),
                )
                for title, channel in cur.fetchall():
                    chunks.append(" ".join(x for x in (title, channel) if x))
                derived = extract_keywords([" ".join(c for c in chunks if c)]) if chunks else []
                user_keywords = derived
            cur.close()
            db_lookup.close()
        except Exception as e:
            print(f"[Coursera Recommend] Cross-platform fallback failed: {e}")

    if not user_keywords:
        return {"error": "No keywords extracted from user history."}

    print(f"[Coursera Recommend] Using keywords: {user_keywords}")

    user_vector = embed_text(" ".join(user_keywords))
    resources = get_courses(" ".join(user_keywords))
    print(f"[Coursera Recommend] Fetched Coursera resources: {len(resources)}")
    if not resources:
        return {
            "source": "coursera",
            "keywords": user_keywords,
            "recommendations": [],
            "message": "No related Coursera courses found. Try broader keywords."
        }

    resource_text = [r['title'] for r in resources]
    resource_vector = embed_text(resource_text)

    similarities = cosine_similarity(user_vector, resource_vector)[0]#compares each vector in resource vector to user_vector and returns a cosine similarity list having same index as resource vector
    top_indexes = similarities.argsort()[::-1][:5]
    recommended_titles = [resources[i] for i in top_indexes]
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user_id_result = cursor.fetchone()
        if not user_id_result:
            return {"error": "Invalid token: user not found."}
        user_id = user_id_result[0]

        cursor.execute("DELETE FROM coursera_recommendations WHERE user_id = %s", (user_id,))

        for course in recommended_titles:
            cursor.execute("""
                INSERT INTO coursera_recommendations 
                (user_id, course_title, provider, enrolled, rating, fetched_at, url, info)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                course["title"],
                course["provider"],
                course["ppl"],
                course["star"],
                datetime.now(),
                course["url"],
                course["info"]
            ))

        db.commit()
    except Exception as e:
        print("DB Error (Coursera recommendations):", e)

    return {
    "source": "coursera",
    "keywords": user_keywords,
    "scores": similarities.tolist()[:5],
    "recommendations": [
        {
            "title": course["title"],
            "url": course["url"],
            "provider":course["provider"],
            "star":course["star"],
            "ppl":course["ppl"],
            "info":course["info"]
        }
        for course in recommended_titles
    ]
}
# ---------------------------------------------------------------------------
# Jobs (SerpApi / Google Jobs)
# ---------------------------------------------------------------------------

class LocationPayload(BaseModel):
    email: str
    city: str | None = None
    region: str | None = None
    country: str | None = None
    country_code: str | None = None


# Minimal locale → (country, country_code) map. We only need enough
# coverage to seed the SerpApi query when the frontend hasn't called
# /profile/location yet. The user can be more precise later.
_LOCALE_COUNTRY: dict[str, tuple[str, str]] = {
    "en-us": ("United States", "us"),
    "en-gb": ("United Kingdom", "gb"),
    "en-in": ("India", "in"),
    "en-ca": ("Canada", "ca"),
    "en-au": ("Australia", "au"),
    "en-nz": ("New Zealand", "nz"),
    "en-ie": ("Ireland", "ie"),
    "en-sg": ("Singapore", "sg"),
    "en-za": ("South Africa", "za"),
    "fr-fr": ("France", "fr"),
    "fr-ca": ("Canada", "ca"),
    "de-de": ("Germany", "de"),
    "es-es": ("Spain", "es"),
    "es-mx": ("Mexico", "mx"),
    "pt-br": ("Brazil", "br"),
    "pt-pt": ("Portugal", "pt"),
    "it-it": ("Italy", "it"),
    "ja-jp": ("Japan", "jp"),
    "ko-kr": ("South Korea", "kr"),
    "zh-cn": ("China", "cn"),
    "zh-tw": ("Taiwan", "tw"),
    "ru-ru": ("Russia", "ru"),
    "nl-nl": ("Netherlands", "nl"),
}


def _derive_country_from_locale(locale: str | None) -> tuple[str | None, str | None]:
    if not locale:
        return None, None
    return _LOCALE_COUNTRY.get(locale.lower(), (None, None))


def _build_location_string(city, region, country) -> str | None:
    parts = [p for p in (city, region, country) if p]
    return ", ".join(parts) if parts else None


# Vocabulary that's natural in learning content (Coursera/YouTube titles,
# tutorial repo names) but actively hurts a Google Jobs search. SerpApi
# treats the query string fairly literally, so a phrase like
# "tensorflow course" pulls in roles *titled* "course" — almost none.
_JOB_QUERY_STOPWORDS: frozenset[str] = frozenset({
    "course", "courses", "tutorial", "tutorials", "lesson", "lessons",
    "introduction", "intro", "fundamentals", "basics", "beginner",
    "advanced", "guide", "guides", "specialization", "certificate",
    "certification", "learn", "learning", "study", "training",
    "bootcamp", "masterclass", "crash", "complete", "ultimate",
    "step", "steps", "video", "videos", "tips", "tricks", "review",
    "implementation",
})


# Map domain keywords → the role-shaped query they imply. Google Jobs
# searches return drastically better results for actual job titles
# ("machine learning engineer") than for skill tokens ("tensorflow").
# First substring hit wins, so order from most specific to most generic.
_DOMAIN_ROLE_MAP: list[tuple[tuple[str, ...], str]] = [
    # ML / data science
    (("machine learning", "deep learning", "tensorflow", "pytorch",
      "keras", "huggingface", "transformer", "nlp"), "machine learning engineer"),
    (("data science", "pandas", "numpy", "jupyter", "scikit"), "data scientist"),
    (("data engineering", "spark", "airflow", "kafka", "etl"), "data engineer"),
    # Web
    (("react", "next.js", "nextjs", "vue", "angular", "frontend",
      "tailwind"), "frontend developer"),
    (("django", "flask", "fastapi", "spring", "rails", "express",
      "node.js", "backend"), "backend developer"),
    (("full stack", "fullstack"), "full stack developer"),
    # Mobile
    (("android", "kotlin"), "android developer"),
    (("ios", "swift"), "ios developer"),
    (("flutter", "react native"), "mobile developer"),
    # Cloud / DevOps / SRE
    (("kubernetes", "docker", "terraform", "ansible"), "devops engineer"),
    (("aws", "azure", "gcp", "cloud"), "cloud engineer"),
    (("site reliability", "sre"), "site reliability engineer"),
    # Security
    (("cybersecurity", "security"), "security engineer"),
    # Game / graphics
    (("unity", "unreal", "game"), "game developer"),
]


def _role_from_signals(keyphrases: list[str], language: str | None) -> str:
    """Pick the most appropriate role-shaped phrase for the SerpApi query.

    We search the cleaned keyphrases for known domain markers first
    (e.g. "tensorflow" → "machine learning engineer"). Falls back to
    "<language> developer" if we have a language, else
    "software developer".
    """
    haystack = " ".join(keyphrases).lower()
    for markers, role in _DOMAIN_ROLE_MAP:
        if any(m in haystack for m in markers):
            return role
    if language:
        return f"{language} developer"
    return "software developer"


def _clean_job_keyphrases(keyphrases: list[str]) -> list[str]:
    """Strip learning-oriented tokens and dedupe."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for phrase in keyphrases:
        tokens = [t for t in phrase.split() if t.lower() not in _JOB_QUERY_STOPWORDS]
        if not tokens:
            continue
        normalized = " ".join(tokens).strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(" ".join(tokens))
    return cleaned


def _derive_job_query_for_user(user_id: int) -> str:
    """Build a job-shaped SerpApi ``q`` from the user's strongest signals.

    Differences from the keyword pipeline used for learning content:
      * Only GitHub + YouTube are sampled. Coursera titles are full of
        words like "course"/"specialization"/"fundamentals" that turn
        a job search into a tutorial search.
      * After extracting keyphrases we strip a stopword list of
        learning-only vocabulary (the same words sneak into tutorial
        repo names and educational video titles).
      * The dominant GitHub language is prepended ("Python", "Go", …)
        so the query looks like something a person would actually type
        into Google Jobs ("Python machine learning" not "machine
        learning").
    """
    db = get_db()
    cursor = db.cursor()
    text_chunks: list[str] = []
    languages: list[str] = []
    try:
        cursor.execute(
            "SELECT repo_name, description, language FROM github_recommendations WHERE user_id = %s LIMIT 25",
            (user_id,),
        )
        for name, desc, lang in cursor.fetchall():
            text_chunks.append(" ".join(x for x in (name, desc) if x))
            if lang and lang != "Unknown":
                languages.append(lang)

        cursor.execute(
            "SELECT title FROM youtube_recommendations WHERE user_id = %s LIMIT 25",
            (user_id,),
        )
        for (title,) in cursor.fetchall():
            if title:
                text_chunks.append(title)
        # Intentionally skipping coursera_recommendations — its titles
        # are dominated by "course"/"specialization"/"fundamentals".
    finally:
        cursor.close()
        db.close()

    text = " ".join(c for c in text_chunks if c).strip()
    if not text:
        return ""

    keyphrases = extract_keywords([text], top_n=5) or []
    cleaned = _clean_job_keyphrases(keyphrases)

    top_language = ""
    if languages:
        from collections import Counter
        top_language = Counter(languages).most_common(1)[0][0]

    # The role anchor is the most important part of a Google Jobs query
    # ("machine learning engineer" returns thousands of hits, while
    # "tensorflow deeplearn" returns none). We always include one.
    role = _role_from_signals(cleaned, top_language or None)
    return role


def _fetch_serpapi_jobs(query: str, location: str | None, gl: str, hl: str) -> list[dict]:
    if not SERPAPI_KEY:
        print("[jobs] SERPAPI_KEY not configured; skipping job fetch")
        return []
    params = {
        "engine": "google_jobs",
        "q": query,
        "google_domain": "google.com",
        "hl": hl or "en",
        "gl": gl or "us",
        "api_key": SERPAPI_KEY,
    }
    if location:
        params["location"] = location
    try:
        res = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
        if res.status_code != 200:
            print(f"[jobs] SerpApi error {res.status_code}: {res.text[:200]}")
            return []
        return res.json().get("jobs_results") or []
    except Exception as e:
        print(f"[jobs] SerpApi request failed: {e}")
        return []


def _normalize_job(raw: dict) -> dict:
    detected = raw.get("detected_extensions") or {}
    apply_options = raw.get("apply_options") or []
    apply_link = apply_options[0].get("link") if apply_options else raw.get("share_link")
    return {
        "job_id": (raw.get("job_id") or "")[:512],
        "title": (raw.get("title") or "")[:500],
        "company_name": (raw.get("company_name") or "")[:255],
        "location": (raw.get("location") or "")[:255],
        "via": (raw.get("via") or "")[:255],
        "description": raw.get("description") or "",
        "thumbnail": raw.get("thumbnail") or "",
        "share_link": raw.get("share_link") or "",
        "apply_link": apply_link or "",
        "posted_at": (detected.get("posted_at") or "")[:64],
        "schedule_type": (detected.get("schedule_type") or "")[:64],
    }


@app.post("/profile/location")
def update_user_location(payload: LocationPayload):
    """Persist the user's reported location for downstream features.

    The frontend calls a public IP-geolocation service from the user's
    browser and POSTs the result here. We store it on the ``users``
    row, replacing any previous value.
    """
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (payload.email,))
        row = cursor.fetchone()
        if not row:
            return {"error": "User not found"}
        user_id = row[0]

        cursor.execute(
            """
            UPDATE users
            SET city = %s,
                region = %s,
                country = %s,
                country_code = %s,
                location_updated_at = %s
            WHERE id = %s
            """,
            (
                payload.city,
                payload.region,
                payload.country,
                (payload.country_code or "").lower() or None,
                datetime.now(),
                user_id,
            ),
        )
        db.commit()
        return {"ok": True}
    except Exception as e:
        print(f"[profile/location] error: {e}")
        return {"error": str(e)}
    finally:
        cursor.close()
        db.close()


@app.get("/get_jobs")
def get_jobs(email: str, query: str | None = None, location: str | None = None):
    """Fetch + persist Google Jobs results for the user.

    Query is derived from the user's existing recommendations if not
    explicitly provided. Location is built from the ``users`` row
    (city/region/country), falling back to the Google ``locale`` we
    captured at OAuth time. Results are cached in
    ``job_recommendations`` and returned to the caller.
    """
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            SELECT id, locale, country, region, city, country_code
            FROM users WHERE email = %s
            """,
            (email,),
        )
        row = cursor.fetchone()
        if not row:
            return {"error": "User not found"}
        user_id, locale, country, region, city, country_code = row

        loc_country, loc_cc = _derive_country_from_locale(locale)
        effective_country = country or loc_country
        effective_country_code = (country_code or loc_cc or "us").lower()
        hl = (locale.split("-")[0] if locale else "en") or "en"

        effective_location = location or _build_location_string(city, region, effective_country)

        effective_query = (query or _derive_job_query_for_user(user_id) or "software developer").strip()

        print(
            f"[jobs] user={email} q={effective_query!r} location={effective_location!r} "
            f"gl={effective_country_code} hl={hl}"
        )

        raw_jobs = _fetch_serpapi_jobs(
            query=effective_query,
            location=effective_location,
            gl=effective_country_code,
            hl=hl,
        )
        normalized = [_normalize_job(j) for j in raw_jobs[:15]]

        # Refresh the cache: clear stale rows, insert fresh ones.
        cursor.execute("DELETE FROM job_recommendations WHERE user_id = %s", (user_id,))
        now = datetime.now()
        for job in normalized:
            cursor.execute(
                """
                INSERT INTO job_recommendations
                (user_id, job_id, title, company_name, location, via,
                 description, thumbnail, share_link, apply_link,
                 posted_at, schedule_type, query_used, location_used, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    job["job_id"],
                    job["title"],
                    job["company_name"],
                    job["location"],
                    job["via"],
                    job["description"],
                    job["thumbnail"],
                    job["share_link"],
                    job["apply_link"],
                    job["posted_at"],
                    job["schedule_type"],
                    effective_query[:255],
                    (effective_location or "")[:255],
                    now,
                ),
            )
        db.commit()

        return {
            "source": "google_jobs",
            "query": effective_query,
            "location": effective_location,
            "count": len(normalized),
            "jobs": normalized,
        }
    except Exception as e:
        print(f"[jobs] error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return {"error": str(e)}
    finally:
        cursor.close()
        db.close()


@app.get("/get_job_recommendations")
def get_job_recommendations(email: str):
    """Return the cached job recommendations for the user."""
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()
        if not row:
            return {"error": "User not found"}
        user_id = row[0]

        cursor.execute(
            """
            SELECT job_id, title, company_name, location, via, description,
                   thumbnail, share_link, apply_link, posted_at, schedule_type,
                   query_used, location_used, fetched_at
            FROM job_recommendations
            WHERE user_id = %s
            ORDER BY fetched_at DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        db.close()

    return [
        {
            "jobId": r[0],
            "title": r[1],
            "companyName": r[2],
            "location": r[3],
            "via": r[4],
            "description": r[5],
            "thumbnail": r[6],
            "shareLink": r[7],
            "applyLink": r[8],
            "postedAt": r[9],
            "scheduleType": r[10],
            "queryUsed": r[11],
            "locationUsed": r[12],
            "fetchedAt": r[13].isoformat() if r[13] else None,
        }
        for r in rows
    ]


@app.get("/debug/session")
def debug_session(request: Request):
    # Test setting a simple session
    request.session["test"] = "hello"
    return {
        "session_keys": list(request.session.keys()),
        "session_data": dict(request.session),
        "cookies": dict(request.cookies)
    }

@app.get("/debug/session/check")
def check_session(request: Request):
    return {
        "session_keys": list(request.session.keys()),
        "session_data": dict(request.session),
        "test_value": request.session.get("test"),
        "cookies": dict(request.cookies)
    }