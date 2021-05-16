import itertools
from typing import Optional

from bs4 import BeautifulSoup
from bs4.element import Tag
import httpx

from .bbcode import to_bbcode
from .data import Badge, Contact, EmbeddedJournal, EmbeddedSubmission, Question, \
    Shout, Special, Stats, UserProfile, WatchInfo
from .util import FA_BASE, format_date, get_direct_text, get_subtitle_num, \
    normalize_url, not_class

def get_user_list(body: Tag) -> list[str]:
    if not (table := body.table):
        return []
    
    return [td.get_text() for td in table.find_all("td")]

def get_special(tag: Tag) -> Optional[Special]:
    if not (img := tag.img):
        return None
    
    return Special(
        id=not_class(img, "inline").replace("-icon", "").replace("-logo", ""),
        img=normalize_url(img["src"]),
        title=img["title"],
    )

def get_profile(client: httpx.Client, username: str) -> UserProfile:
    r = client.get(f"{FA_BASE}/user/{username}/")
    soup = BeautifulSoup(r.text, "lxml")

    user_block = soup.find("div", class_="username")
    name_block = user_block.select_one("h2 span")
    username = username[1:] if (username := name_block.get_text().strip())[0] in "~!∞" else username
    status = name_block["title"].split(": ")[-1].lower()
    special = get_special(name_block)
    title, _, joined = user_block.find("span", class_="font-small").get_text().strip().rpartition(" | ")
    title = title if title else None
    joined = format_date(joined.split(": ")[-1])
    avatar = normalize_url(soup.find("img", class_="user-nav-avatar")["src"])

    profile_block = soup.find("div", class_="userpage-profile")
    profile = to_bbcode(profile_block)

    user = UserProfile(
        username=username,
        status=status,
        special=special,
        title=title,
        joined=joined,
        avatar=avatar,
        profile=profile,
    )

    layout = soup.find("div", class_="userpage-layout")

    for section in layout.find_all("section"):
        if not (header := section.select_one("div.section-header")):
            for container in section.find_all("div", class_="comment_container"):
                username = container.find("div", class_="comment_username")
                user.shouts.append(Shout(
                    username=username.get_text(),
                    special=get_special(username),
                    avatar=normalize_url(container.find("img", class_="comment_useravatar")["src"]),
                    time=format_date(container.find("span", class_="popup_date").get_text()),
                    text=to_bbcode(container.find("div", class_="comment_text")),
                ))
            
            continue

        label = header.h2.get_text()
        bodies = section.find_all("div", class_="section-body")
        body = bodies[0]

        if label == "Recent Watchers":
            user.watchers = WatchInfo(
                num=get_subtitle_num(header),
                recent=get_user_list(body),
            )
        elif label == "Recently Watched":
            user.watched = WatchInfo(
                num=get_subtitle_num(header),
                recent=get_user_list(body),
            )
        elif label == "Stats":
            lines = itertools.chain.from_iterable(cell.get_text().strip().splitlines() for cell in body.find_all("div", class_="cell"))
            nums = [int(line.split(": ")[-1]) for line in lines]
            user.stats = Stats(**{field: value for field, value in zip(Stats.__fields__.keys(), nums)})
        elif label == "Recent Journal":
            link = header.a
            href = link["href"]
            user.journal = EmbeddedJournal(
                id=int(href.split("/")[-1]),
                url=normalize_url(href),
                comments=get_subtitle_num(header),
                title=body.h2.get_text(),
                time=format_date(body.find("span", class_="popup_date")["title"]),
                text=to_bbcode(body.div),
            )
        elif label == "Badges":
            for badge in body.find_all("div", class_="badge"):
                img = badge.img
                user.badges.append(Badge(
                    id=int(badge["id"].split("-")[-1]),
                    name=not_class(badge, "badge"),
                    img=normalize_url(img["src"]),
                    title=img["title"],
                ))
        elif label == "User Profile":
            info = user.info

            if (submission := section.find("div", class_="section-submission")):
                url = submission.a["href"]
                info.submission = EmbeddedSubmission(
                    id=int(url.split("/")[-2]),
                    url=normalize_url(url),
                    img=normalize_url(submission.img["src"]),
                )
            
            rows = section.find_all("div", class_="table-row")
            info.trades, info.commissions = [get_direct_text(row) == "Yes" for row in rows[:2]]
            for row in rows[2:]:
                info.questions.append(Question(
                    question=(question := row.strong.get_text()),
                    answer=to_bbcode(row) if question == "Favorite Artists" else get_direct_text(row),
                ))
            
            if (contacts := section.find("div", class_="user-contact")):
                for item in contacts.find_all("div", class_="user-contact-item"):
                    site = item.div.div["class"][0].split("-")[-1]
                    if (a := item.a):
                        info.contacts.append(Contact(
                            site=site,
                            id=a.get_text(),
                            url=a["href"],
                        ))
                    else:
                        info.contacts.append(Contact(
                            site=site,
                            id=get_direct_text(item.find("div", class_="user-contact-user-info")),
                            url=None,
                        ))
    
    return user