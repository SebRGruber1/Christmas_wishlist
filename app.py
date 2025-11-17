from flask import Flask, render_template, request, redirect, url_for
import json
import os
from datetime import datetime


app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Path to the JSON file where wishlist items are stored
FILE_PATH = "wishlist_data.json"


def load_data():
    """
    Load the wishlist items from the JSON file. If the file does not exist,
    return an empty list. Reading the file on each request ensures that
    updates to the JSON file are reflected immediately in the app.
    """
    if os.path.exists(FILE_PATH):
        with open(FILE_PATH) as f:
            return json.load(f)
    return []


def save_data(data):
    """
    Persist the provided list of wishlist items to the JSON file.
    """
    with open(FILE_PATH, "w") as f:
        json.dump(data, f)



# Previously this app attempted to scrape images from product URLs using meta tags
# via the `extract_image` function and external libraries (`requests` and
# `BeautifulSoup`). With the new design, users provide their own image URLs,
# so no scraping is needed. The image scraping logic and its dependencies
# have been removed for simplicity.


@app.context_processor
def inject_placeholder():
    """
    Inject a placeholder image URL into the template context. This function
    makes the `placeholder_url` variable available in all templates without
    explicitly passing it when rendering. The placeholder image should
    reside in the `static` folder of your Flask project.
    """
    return {'placeholder_url': url_for('static', filename='placeholder.jpg')}


@app.route('/', methods=["GET", "POST"])
def wishlist():
    """
    Handle both displaying the wishlist and adding new items.

    - On GET requests, this route reads the existing items from the JSON
      file and renders the combined form/list template.
    - On POST requests, it reads form data to create a new item. If the
      user provides an explicit `image_url`, that value is used. If not,
      the app attempts to extract an image from the provided `link`.
      New items are appended to the JSON file, and the user is redirected
      back to the list with a success message.
    """
    data = load_data()
    if request.method == "POST":
        name = request.form['name']
        link = request.form['link']
        notes = request.form['notes']
        image_url = request.form.get('image_url', '').strip()

        # Choose the image: manual first, ignore scraping from the link
        image = image_url or None

        # Create and store the new item. Purchased defaults to False for the owner.
        data.append({
            "name": name,
            "link": link,
            "notes": notes,
            "image": image,
            "purchased": False,
            "created_at": datetime.now().isoformat()
        })
        save_data(data)
        # Redirect back to the owner view. The new item will appear in the list.
        return redirect(url_for('wishlist'))

    # Prepare items for display. Each item includes its index so it can be
    # referenced in the delete URL. We include the purchased flag in case
    # templates want to use it, but the owner view does not surface it.
    items = []
    for idx, item in enumerate(data):
        items.append({
            "index": idx,
            "name": item.get("name", "-"),
            "brand": item.get("brand", ""),
            "link": item.get("link", ""),
            "notes": item.get("notes", ""),
            "image": item.get("image"),
            "purchased": item.get("purchased", False)
        })
    return render_template("wishlist.html", items=items)


@app.route('/delete/<int:index>')
def delete_item(index: int):
    """
    Delete the wish list item at the specified index and redirect back to
    the main list. If the index is out of range, nothing happens.
    """
    data = load_data()
    if 0 <= index < len(data):
        data.pop(index)
        save_data(data)
    return redirect(url_for('wishlist'))

# Legacy route support: redirect old /wishlist and /add URLs to the main list
@app.route('/wishlist')
def wishlist_page():
    """
    Preserve the old /wishlist URL by redirecting to the root wishlist.
    """
    return redirect(url_for('wishlist'))

@app.route('/add')
def add_page():
    """
    Preserve the old /add URL by redirecting to the root wishlist. The main page
    contains the form to add items.
    """
    return redirect(url_for('wishlist'))


@app.route('/public')
def public_view():
    """
    Public view of the wishlist for friends and family. This route displays
    all items, grouped by whether they have been marked as purchased. Items
    that are already reserved are shown crossed out with a disabled button,
    while unreserved items include a button to reserve them. The owner
    should share this URL with gift‑givers.
    """
    data = load_data()
    items = []
    for idx, item in enumerate(data):
        items.append({
            "index": idx,
            "name": item.get("name", "-"),
            "brand": item.get("brand", ""),
            "link": item.get("link", ""),
            "notes": item.get("notes", ""),
            "image": item.get("image"),
            "purchased": item.get("purchased", False)
        })
    return render_template("public_list.html", items=items)


@app.route('/reserve/<int:index>')
def reserve_item(index: int):
    """
    Mark the specified item as purchased (reserved). Called by gift‑givers
    via the public view. After reserving the item, redirect back to the
    public list. If the index is out of range, nothing happens.
    """
    data = load_data()
    if 0 <= index < len(data):
        data[index]['purchased'] = True
        save_data(data)
    return redirect(url_for('public_view'))


@app.route('/unreserve/<int:index>')
def unreserve_item(index: int):
    """
    Remove the purchased flag from the specified item. This provides a way
    for gift‑givers to undo a reservation if they change their mind. After
    unreserving, redirect back to the public list.
    """
    data = load_data()
    if 0 <= index < len(data):
        data[index]['purchased'] = False
        save_data(data)
    return redirect(url_for('public_view'))


if __name__ == '__main__':
    # Running the app with debug=True enables hot reloading and better error pages
    app.run(debug=True)