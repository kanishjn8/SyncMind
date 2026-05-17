from fastapi import APIRouter, Request
from urllib.parse import urlencode
import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
import mysql.connector
from fastapi.responses import RedirectResponse


router = APIRouter()
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)
def get_db():
    return mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    port=int(os.getenv("DB_PORT"))
    )  
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_SCOPE = "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/youtube.readonly"#for reading user data available publicly
GIT_CLIENT_SECRET=os.getenv("GIT_CLIENT_SECRET")
GIT_CLIENT_ID=os.getenv("GIT_CLIENT_ID")
GITHUB_REDIRECT_URI=os.getenv("GITHUB_REDIRECT_URI")

@router.get("/google/login")
def login_with_google():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": YOUTUBE_SCOPE,
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return {"auth_url": auth_url}

def save_tokens_yt(email, access_token, refresh_token, expires_in, platform):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user:
        user_id = user[0]
    else:
        cursor.execute(
            "INSERT INTO users (email) VALUES (%s)",
            (email,)
        )
        user_id = cursor.lastrowid


    query = """
    INSERT INTO user_tokens (user_id, platform, access_token, refresh_token, expires_in)
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        access_token = VALUES(access_token),
        refresh_token = VALUES(refresh_token),
        expires_in = VALUES(expires_in);
    """
    values = (user_id, platform, access_token, refresh_token, expires_in)
    cursor.execute(query, values)

    db.commit()
    cursor.close()
    db.close()
    print("Tokens saved")

def save_user_if_not_exists(email, name, locale: str | None = None):
    conn = get_db()
    cursor = conn.cursor()

    # Insert (or update) the user record, including the Google-provided
    # locale ("en-US", "en-IN", …). The locale is used as a fallback
    # signal for downstream features like job recommendations when the
    # frontend hasn't reported a richer location yet.
    cursor.execute(
        """
        INSERT INTO users (email, name, locale)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            locale = COALESCE(VALUES(locale), users.locale)
        """,
        (email, name, locale),
    )

    conn.commit()
    cursor.close()
    conn.close()
    print("DB SAVED")
temp_sessions={}
@router.get("/google/callback")
def google_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return {"error": "No code provided"}

    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
    if response.status_code != 200:
        return {"error": "Failed to get token", "details": response.text}

    token_json = response.json()
    access_token = token_json.get("access_token")
    refresh_token = token_json.get("refresh_token")
    expires_in = token_json.get("expires_in")

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    userinfo = requests.get("https://openidconnect.googleapis.com/v1/userinfo", headers=headers).json()
    

    email = userinfo.get("email")
    name = userinfo.get("name", "Unknown User")
    locale = userinfo.get("locale")

    save_tokens_yt(email, access_token, refresh_token, expires_in, platform="google")
    save_user_if_not_exists(email, name, locale=locale)

    # Generate a temporary token
    import uuid
    temp_token = str(uuid.uuid4())
    
    # Store session data temporarily - ADD PLATFORM FIELD
    temp_sessions[temp_token] = {
        "email": email,
        "name": name,
        "platform": "google"  
    }
    
    # Redirect with the token
    return RedirectResponse(f"http://localhost:3000?auth_token={temp_token}")

@router.get("/claim")
def claim_session(auth_token: str, request: Request):
    if auth_token in temp_sessions:
        session_data = temp_sessions[auth_token]
        
        # Set the appropriate session based on platform
        if session_data.get("platform") == "github":
            request.session["github_user"] = {
                "email": session_data["email"]
            }
        else:  # Google (or default to Google)
            request.session["google_user"] = {
                "email": session_data["email"],
                "name": session_data["name"]
            }
        
        # Clean up temporary storage
        del temp_sessions[auth_token]
        
        return {"success": True, "user": session_data}
    else:
        return {"success": False, "error": "Invalid or expired token"}
@router.get("/github")
def github_login():
    params = {
        "client_id": GIT_CLIENT_ID,
        "scope": "read:user user:email",
        "redirect_uri": GITHUB_REDIRECT_URI,
    }
    github_auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return {"url": github_auth_url}

def store_github_token(email: str, access_token: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user:
        user_id = user[0]
    else:
        cursor.execute("INSERT INTO users (email) VALUES (%s)",(email,))
        user_id = cursor.lastrowid 

    query = """
        INSERT INTO user_tokens (user_id, platform, access_token)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            access_token = VALUES(access_token),
            updated_at = CURRENT_TIMESTAMP;
    """
    values = (user_id, 'github', access_token)
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    cursor.close()


@router.get("/github/callback")
def github_callback(code: str, request: Request):
    headers = {"Accept": "application/json"}
    data = {
        "client_id": GIT_CLIENT_ID,
        "client_secret": GIT_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GITHUB_REDIRECT_URI
    }

    token_res = requests.post("https://github.com/login/oauth/access_token", headers=headers, data=data)
    token_json = token_res.json()
    access_token = token_json.get("access_token")

    if not access_token:
        return {"error": "Failed to get access token", "details": token_json}

    email_res = requests.get(
        "https://api.github.com/user/emails",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    emails = email_res.json()
    primary_email = None
    if isinstance(emails, list):
        primary_email = next((e.get("email") for e in emails if e.get("primary")), None)
        if not primary_email:
            primary_email = next((e.get("email") for e in emails if e.get("verified")), None)
        if not primary_email and emails:
            primary_email = emails[0].get("email")

    if not primary_email:
        return {"error": "GitHub account email not available. Ensure your email is visible/verified on GitHub."}

    store_github_token(email=primary_email, access_token=access_token)

    # Generate a temporary token (same as Google)
    import uuid
    temp_token = str(uuid.uuid4())
    
    # Store session data temporarily
    temp_sessions[temp_token] = {
        "email": primary_email,
        "platform": "github" 
    }
    
    return RedirectResponse(f"http://localhost:3000?auth_token={temp_token}")

from fastapi import Request
from mysql.connector import connect

@router.get("/user")
def get_user_info(email :str):
  
    if not email:
        return {"error": "User not authenticated"}

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        return {"error": "User not found"}

    return {"user": user, "email":email}

@router.get("/auth/test-session")
def test_session(request: Request):
    print("Session keys:", list(request.session.keys()))
    print("Session data:", request.session)
    return {"session": dict(request.session)}