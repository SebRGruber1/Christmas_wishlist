from flask import (
    Flask, render_template, request, redirect, url_for, session, abort, Response,
    send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import json
import os
import secrets
import shutil
import time
import uuid


# Whose list this is. Shown in the page headings.
OWNER_NAME = "Sebastian"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Everything the app writes lives in data/, which is not tracked by git, so
# deploying new code can never overwrite the live list.
DATA_DIR = os.path.join(BASE_DIR, "data")
FILE_PATH = os.path.join(DATA_DIR, "wishlist.json")
AUTH_PATH = os.path.join(DATA_DIR, "owner_auth.json")
SECRET_PATH = os.path.join(DATA_DIR, "secret_key.txt")
# Photos the owner uploads. Kept with the data so deploys never touch them.
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

# Where the list used to be stored. Older versions used a relative path, so
# the real file may be in the working directory rather than next to app.py.
LEGACY_PATHS = [
    os.path.abspath("wishlist_data.json"),
    os.path.join(BASE_DIR, "wishlist_data.json"),
]

os.makedirs(UPLOAD_DIR, exist_ok=True)


def _load_secret_key():
    """Create a random session key on first run and reuse it afterwards."""
    if not os.path.exists(SECRET_PATH):
        with open(SECRET_PATH, "w") as f:
            f.write(secrets.token_hex(32))
    with open(SECRET_PATH) as f:
        return f.read().strip()


app = Flask(__name__)
app.secret_key = _load_secret_key()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=90),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,  # largest upload accepted: 8 MB
)


# ---------------------------------------------------------------- storage

def save_data(data):
    """Write the list to disk via a temp file so a crash can't corrupt it."""
    tmp = FILE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, FILE_PATH)


def load_data():
    """
    Load the wishlist. On the first run after upgrading, copy the list over
    from its old location. Every item gets a permanent id so that buttons
    always act on the item they were shown next to.
    """
    if not os.path.exists(FILE_PATH):
        for legacy in LEGACY_PATHS:
            if os.path.exists(legacy):
                shutil.copyfile(legacy, FILE_PATH)
                break
        else:
            return []

    with open(FILE_PATH) as f:
        data = json.load(f)

    changed = False
    for item in data:
        if not item.get("id"):
            item["id"] = uuid.uuid4().hex[:12]
            changed = True
    if changed:
        save_data(data)
    return data


def find_item(data, item_id):
    for item in data:
        if item.get("id") == item_id:
            return item
    return None


# ---------------------------------------------------------------- uploads

# Recognise real image files by their first bytes rather than trusting the
# file name. Maps signature -> extension.
IMAGE_SIGNATURES = [
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
]


def save_upload(file_storage):
    """
    Save an uploaded photo and return the address to show it from, or None
    if nothing usable was uploaded.
    """
    if not file_storage or not file_storage.filename:
        return None
    head = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    ext = None
    for signature, extension in IMAGE_SIGNATURES:
        if head.startswith(signature):
            ext = extension
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        ext = "webp"
    if ext is None:
        return None
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_DIR, filename))
    return url_for("uploaded_file", filename=filename)


def delete_upload(image):
    """Remove an item's uploaded photo from disk, if it has one."""
    prefix = "/uploads/"
    if image and image.startswith(prefix):
        path = os.path.join(UPLOAD_DIR, os.path.basename(image[len(prefix):]))
        if os.path.exists(path):
            os.remove(path)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename, max_age=60 * 60 * 24 * 30)


# ------------------------------------------------------------------- auth

def password_is_set():
    return os.path.exists(AUTH_PATH)


def owner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("owner"):
            target = request.full_path if request.method == "GET" else None
            return redirect(url_for("login", next=target))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Owner sign-in. The very first visit asks the owner to choose a password;
    after that it asks for it. Only a hash of the password is stored.
    """
    setup = not password_is_set()
    error = None
    # Only ever send people back to a page on this site.
    next_url = request.values.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("wishlist")
    if request.method == "POST":
        password = request.form.get("password", "")
        if setup:
            if len(password) < 8:
                error = "Please choose a password of at least 8 characters."
            elif password != request.form.get("confirm", ""):
                error = "The two passwords don't match."
            else:
                with open(AUTH_PATH, "w") as f:
                    json.dump({"hash": generate_password_hash(password)}, f)
                session.permanent = True
                session["owner"] = True
                return redirect(next_url)
        else:
            with open(AUTH_PATH) as f:
                stored = json.load(f)["hash"]
            if check_password_hash(stored, password):
                session.permanent = True
                session["owner"] = True
                return redirect(next_url)
            time.sleep(1)  # slow down guessing
            error = "That password isn't right."
    return render_template("login.html", setup=setup, error=error, next_url=next_url)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("public_view"))


# ---------------------------------------------------------------- helpers

@app.context_processor
def inject_globals():
    return {
        "placeholder_url": url_for("static", filename="placeholder.svg"),
        "owner_name": OWNER_NAME,
        "year": datetime.now().year,
    }


@app.after_request
def no_index(response):
    """Ask search engines not to list any page of this site."""
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")


# ------------------------------------------------------------ owner pages

@app.route("/", methods=["GET", "POST"])
@owner_required
def wishlist():
    """The owner's page: add items and remove them."""
    data = load_data()
    if request.method == "POST":
        data.append({
            "id": uuid.uuid4().hex[:12],
            "name": request.form["name"].strip(),
            "brand": request.form.get("brand", "").strip(),
            "link": request.form.get("link", "").strip(),
            "notes": request.form.get("notes", "").strip(),
            # An uploaded photo wins over a pasted picture address.
            "image": save_upload(request.files.get("image_file"))
                     or request.form.get("image_url", "").strip() or None,
            "purchased": False,
            "created_at": datetime.now().isoformat(),
        })
        save_data(data)
        return redirect(url_for("wishlist"))

    return render_template("wishlist.html", items=data)


@app.route("/delete/<item_id>", methods=["POST"])
@owner_required
def delete_item(item_id):
    data = load_data()
    item = find_item(data, item_id)
    if item:
        data.remove(item)
        save_data(data)
        delete_upload(item.get("image"))
    return redirect(url_for("wishlist"))


# Old addresses that people may still have bookmarked.
@app.route("/wishlist")
@app.route("/add")
def legacy_redirect():
    return redirect(url_for("wishlist"))


# ----------------------------------------------------------- shared pages

@app.route("/public")
def public_view():
    """The page shared with family and friends."""
    data = load_data()
    available = [i for i in data if not i.get("purchased")]
    taken = [i for i in data if i.get("purchased")]
    return render_template("public_list.html", available=available, taken=taken)


def _set_purchased(item_id, value):
    data = load_data()
    item = find_item(data, item_id)
    if item is None:
        abort(404)
    item["purchased"] = value
    save_data(data)
    return redirect(url_for("public_view"))


# These only accept POST (a real button press), so link previews in chat
# apps and search crawlers can't claim or unclaim gifts by visiting a link.
@app.route("/reserve/<item_id>", methods=["POST"])
def reserve_item(item_id):
    return _set_purchased(item_id, True)


@app.route("/unreserve/<item_id>", methods=["POST"])
def unreserve_item(item_id):
    return _set_purchased(item_id, False)


if __name__ == "__main__":
    app.run(debug=True)
