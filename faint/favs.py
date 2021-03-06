import sys

from httpx import Client

from .data import Favorite, Settings
from .util import cleave, FA_BASE, format_date, get_page_soup, normalize_url, not_class

def get_favs(client: Client, settings: Settings) -> list[Favorite]:
    base = f"{FA_BASE}/favorites/{settings.username}/"
    url = base
    favs = []
    
    while True:
        soup = get_page_soup(client, url)
        page_favs = soup.select("figure[data-fav-id]")

        try:
            last_fav_time = format_date(soup.select_one("div.midsection span")["title"], settings)
        except TypeError:
            if soup.find("div", id="no-images"):
                break
            else:
                print(f"User {settings.username} not found!")
                sys.exit(1)

        url = base + page_favs[0]["data-fav-id"] + "/next/"

        # Reverse chronological order: we're not there yet
        if settings.before < last_fav_time:
            continue
        # We're all done - no more inside the range
        elif settings.after > last_fav_time:
            break
        
        first = page_favs[0]
        favs.append(Favorite(
            sid=int(first["id"].replace("sid-", "")),
            rating=cleave(not_class(first, "t-image")),
            username=first["data-user"].replace("u-", ""),
            id=first["data-fav-id"],
            time=last_fav_time,
            url=normalize_url(first.find("a")["href"]),
        ))
        
        if len(page_favs) == 1:
            break
    
    return favs