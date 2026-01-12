import os
import sqlite3
import requests
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from passlib.context import CryptContext
from datetime import date

# ---------------- CONFIG ----------------
AI_ENGINE_URL = "https://randa-leggy-ronald.ngrok-free.dev"
DB_PATH = os.getenv("DB_PATH", "users.db")

app = FastAPI()

# ---------------- DATABASE ----------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password TEXT,
    credits INTEGER,
    last_reset TEXT
)
""")
conn.commit()

# ---------------- SECURITY (NO BCRYPT) ----------------
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password):
    return pwd_context.hash(password)

def verify_password(password, hashed):
    return pwd_context.verify(password, hashed)

# ---------------- CREDITS ----------------
DAILY_CREDITS = 5

def reset_daily_credits(email):
    today = str(date.today())
    user = c.execute("SELECT credits,last_reset FROM users WHERE email=?", (email,)).fetchone()

    if user and user[1] != today:
        c.execute(
            "UPDATE users SET credits=?, last_reset=? WHERE email=?",
            (DAILY_CREDITS, today, email)
        )
        conn.commit()

# ---------------- UI ----------------

LOGIN_PAGE = """
<html><body style="background:#0e0e10;color:white;font-family:Arial">
<div style="width:400px;margin:100px auto">
<h2>Login</h2>
<form method="post" action="/login">
<input name="email" placeholder="Email" required><br><br>
<input name="password" type="password" placeholder="Password" required><br><br>
<button>Login</button>
</form>
<a href="/signup" style="color:white">Create account</a>
</div></body></html>
"""

SIGNUP_PAGE = """
<html><body style="background:#0e0e10;color:white;font-family:Arial">
<div style="width:400px;margin:100px auto">
<h2>Signup</h2>
<form method="post" action="/signup">
<input name="email" placeholder="Email" required><br><br>
<input name="password" type="password" placeholder="Password" required><br><br>
<button>Create Account</button>
</form>
</div></body></html>
"""

DASHBOARD = """
<html><body style="background:#0e0e10;color:white;font-family:Arial">
<div style="width:600px;margin:50px auto">
<h1>AI Video Generator</h1>
<p>Credits today: {credits}</p>
<form method="post" action="/generate">
<input type="hidden" name="email" value="{email}">
<input name="prompt" placeholder="Describe your video..." required><br><br>
<button>Generate Video</button>
</form>
<p>{message}</p>
</div></body></html>
"""

# ---------------- ROUTES ----------------

@app.get("/", response_class=HTMLResponse)
def home():
    return RedirectResponse("/login")

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return LOGIN_PAGE

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if not user or not verify_password(password, user[2]):
        return HTMLResponse("<h3>Invalid login</h3><a href='/login'>Try again</a>")

    return RedirectResponse(f"/dashboard?email={email}", status_code=302)

@app.get("/signup", response_class=HTMLResponse)
def signup_page():
    return SIGNUP_PAGE

@app.post("/signup")
def signup(email: str = Form(...), password: str = Form(...)):
    try:
        c.execute(
            "INSERT INTO users (email,password,credits,last_reset) VALUES (?,?,?,?)",
            (email, hash_password(password), DAILY_CREDITS, str(date.today()))
        )
        conn.commit()
        return RedirectResponse("/login", status_code=302)

    except sqlite3.IntegrityError:
        return HTMLResponse("<h3>Email already exists</h3><a href='/signup'>Try again</a>")

    except Exception as e:
        return HTMLResponse(f"<h3>Signup error</h3><pre>{e}</pre>")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(email: str):
    reset_daily_credits(email)

    row = c.execute("SELECT credits FROM users WHERE email=?", (email,)).fetchone()
    credits = row[0] if row else 0

    html = DASHBOARD.replace("{credits}", str(credits)) \
                    .replace("{email}", email) \
                    .replace("{message}", "")

    return html

@app.post("/generate")
def generate(prompt: str = Form(...), email: str = Form(...)):
    try:
        res = requests.get(
            f"{AI_ENGINE_URL}/generate",
            params={"prompt": prompt},
            timeout=600
        )

        data = res.json()
        video_url = f"{AI_ENGINE_URL}/video/{data['video']}"

        return HTMLResponse(
            f"<h2>Your AI Video is Ready</h2>"
            f"<video src='{video_url}' controls style='width:100%'></video><br><br>"
            f"<a href='/dashboard?email={email}'>Back</a>"
        )

    except Exception as e:
        return HTMLResponse(f"<h3>AI Engine Error</h3><pre>{e}</pre>")
