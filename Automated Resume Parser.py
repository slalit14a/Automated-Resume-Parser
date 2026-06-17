from flask import Flask, request, redirect, session
import sqlite3
import bcrypt
import os
import pdfplumber
import re

app = Flask(__name__)
app.secret_key = "new_db_project_key"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

#DATABASE
def init_db():

    conn = sqlite3.connect("final_resume.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password BLOB
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS resumes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        name TEXT,
        email TEXT,
        skills TEXT,
        education TEXT,
        filename TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

#EXTRACT DATA
def extract_data(text):

    email = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    email = email[0] if email else "Not Found"

    name = text.split("\n")[0] if text else "Not Found"

    skills_list = ["python", "java", "c++", "html", "css", "sql"]
    skills = [s for s in skills_list if s in text.lower()]

    education_list = ["bca", "btech", "mca", "degree", "college", "university"]
    education = [e for e in education_list if e in text.lower()]

    return name, email, ",".join(skills), ",".join(education)

#SCORE FUNCTION
def calculate_score(text, keyword):

    text = text.lower()
    words = keyword.lower().split()

    match = 0
    for w in words:
        if w in text:
            match += 1

    if len(words) == 0:
        return 0

    return int((match / len(words)) * 100)

#HOME
@app.route("/")
def home():

    if "user" in session:
        return redirect("/dashboard")

    return """
    <h1>Resume Parser System</h1>
    <a href="/register">Register</a><br><br>
    <a href="/login">Login</a>
    """

#REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        try:
            conn = sqlite3.connect("final_resume.db")
            c = conn.cursor()

            c.execute("INSERT INTO users(username,password) VALUES(?,?)",
                      (username, hashed))

            conn.commit()
            conn.close()

            return "<h2>Registered Successfully</h2><a href='/login'>Login</a>"

        except sqlite3.IntegrityError:
            return "<h2>User Already Exists</h2>"

    return """
    <h2>Register</h2>
    <form method="POST">
        Username:<br>
        <input type="text" name="username"><br><br>

        Password:<br>
        <input type="password" name="password"><br><br>

        <button type="submit">Register</button>
    </form>
    """

#LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("final_resume.db")
        c = conn.cursor()

        c.execute("SELECT password FROM users WHERE username=?", (username,))
        user = c.fetchone()

        conn.close()

        if user and bcrypt.checkpw(password.encode("utf-8"), user[0]):
            session["user"] = username
            return redirect("/dashboard")

        return "<h2>Invalid Login</h2>"

    return """
    <h2>Login</h2>
    <form method="POST">
        Username:<br>
        <input type="text" name="username"><br><br>

        Password:<br>
        <input type="password" name="password"><br><br>

        <button type="submit">Login</button>
    </form>
    """

#DASHBOARD
@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/login")

    return f"""
    <h1>Welcome {session['user']}</h1>
    <a href="/upload">Upload Resume</a><br><br>
    <a href="/search">Search Resume</a><br><br>
    <a href="/logout">Logout</a>
    """

#UPLOAD
@app.route("/upload", methods=["GET", "POST"])
def upload():

    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":

        file = request.files["resume"]

        if not file.filename.lower().endswith(".pdf"):
            return "<h2>Only PDF Allowed</h2>"

        path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(path)

        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

        name, email, skills, education = extract_data(text)

        conn = sqlite3.connect("final_resume.db")
        c = conn.cursor()

        c.execute("""
        INSERT INTO resumes(username,name,email,skills,education,filename)
        VALUES(?,?,?,?,?,?)
        """, (session["user"], name, email, skills, education, file.filename))

        conn.commit()
        conn.close()

        return "<h2>Resume Uploaded Successfully</h2><a href='/dashboard'>Back</a>"

    return """
    <h2>Upload Resume</h2>
    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="resume"><br><br>
        <button type="submit">Upload</button>
    </form>
    """

# SEARCH
@app.route("/search", methods=["GET", "POST"])
def search():

    if "user" not in session:
        return redirect("/login")

    result = ""

    if request.method == "POST":

        keyword = request.form["keyword"]

        conn = sqlite3.connect("final_resume.db")
        c = conn.cursor()

        c.execute("""
        SELECT name,email,skills,education,filename
        FROM resumes
        WHERE name LIKE ? OR skills LIKE ? OR education LIKE ?
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))

        rows = c.fetchall()
        conn.close()

        # SORT BY SCORE (BEST FIRST)
        rows = list(rows)

        rows.sort(
            key=lambda r: calculate_score(
                f"{r[0]} {r[1]} {r[2]} {r[3]} {r[4]}",
                keyword
            ),
            reverse=True
        )

        for r in rows:

            score = calculate_score(
                f"{r[0]} {r[1]} {r[2]} {r[3]} {r[4]}",
                keyword
            )

            result += f"""
            <div style="
                border:1px solid #ccc;
                padding:15px;
                margin:10px;
                border-radius:10px;
                background:#f9f9f9;
            ">
                <h3>🔥 Match Score: {score}%</h3>

                <b>Name:</b> {r[0]} <br>
                <b>Email:</b> {r[1]} <br>
                <b>Skills:</b> {r[2].title()} <br>
                <b>Education:</b> {r[3].title()} <br>
                <b>File:</b> {r[4]} <br>
            </div>
            """

    return f"""
    <h2>ATS Resume Search</h2>

    <form method="POST">
        <input type="text" name="keyword" placeholder="Search skills...">
        <button type="submit">Search</button>
    </form>

    <br>
    {result}
    """

#LOGOUT 
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

# RUN 
if __name__ == "__main__":
    app.run(debug=True)