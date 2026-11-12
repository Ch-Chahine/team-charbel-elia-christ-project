"""
api_client.py  --  ALL calls to your external API live here (one place).

RIGHT NOW this returns a few SAMPLE items so the app runs out of the box.
TODO (your team): replace the sample data with real calls to your chosen free
API, keeping the SAME return shapes so the rest of the app keeps working:

    search(query)   -> a list of dicts, each: {"id", "title", "image"}
    get_item(id)    -> one dict: {"id", "title", "image", "description"}
"""
import requests  # you'll use this for the real API calls

TIMEOUT = 6  # seconds; give up instead of hanging if the API is slow

# ----- temporary sample data (delete once your API works) -----
_SAMPLE = [
    {"id": "1", "title": "Example Item One",
     "image": "https://picsum.photos/id/1011/400/300",
     "description": "Replace this with a real description from your API."},
    {"id": "2", "title": "Example Item Two",
     "image": "https://picsum.photos/id/1025/400/300",
     "description": "Replace this with a real description from your API."},
    {"id": "3", "title": "Example Item Three",
     "image": "https://picsum.photos/id/1039/400/300",
     "description": "Replace this with a real description from your API."},
]


def search(query):
    """Return a list of items matching the query."""
    # TODO: call your API instead, e.g.
    #   r = requests.get("https://api.example.com/search",
    #                    params={"q": query}, timeout=TIMEOUT)
    #   if r.status_code != 200:
    #       return []
    #   data = r.json()
    #   return [{"id": x["id"], "title": x["name"], "image": x["thumb"]}
    #           for x in data["results"]]
    q = query.lower()
    hits = [it for it in _SAMPLE if q in it["title"].lower()]
    return hits or _SAMPLE


def get_item(item_id):
    """Return one item by its id, or None if not found."""
    # TODO: call your API for one item, e.g.
    #   r = requests.get(f"https://api.example.com/item/{item_id}", timeout=TIMEOUT)
    #   ...
    for it in _SAMPLE:
        if it["id"] == item_id:
            return it
    return None
