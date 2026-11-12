import json
import os
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = "AbyssTraveler08"
TOKEN = os.environ["GITHUB_TOKEN"]
API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "AbyssTraveler08-profile-stats",
}

def get_json(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=HEADERS, method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

def svg_card(title, width, height, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#171b2b"/><stop offset="1" stop-color="#202b45"/></linearGradient></defs>
<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="16" fill="url(#bg)" stroke="#344563"/>
<text x="28" y="42" fill="#79aaff" font-family="Arial,sans-serif" font-size="23" font-weight="700">{escape(title)}</text>
{body}
</svg>'''

def metric(x, y, value, label):
    return (f'<text x="{x}" y="{y}" fill="#f1f5ff" font-family="Arial,sans-serif" '
            f'font-size="30" font-weight="700">{escape(str(value))}</text>'
            f'<text x="{x}" y="{y+25}" fill="#9eacc7" font-family="Arial,sans-serif" '
            f'font-size="13">{escape(label)}</text>')

def main():
    today = date.today()
    since = today - timedelta(days=364)
    user = get_json(f"{API}/users/{USERNAME}")
    repos = get_json(f"{API}/users/{USERNAME}/repos?type=owner&per_page=100&sort=updated")
    stars = sum(repo.get("stargazers_count", 0) for repo in repos)
    forks = sum(repo.get("forks_count", 0) for repo in repos)
    language_totals = Counter()
    for repo in repos:
        if repo.get("fork") or not repo.get("size"):
            continue
        try:
            languages = get_json(repo["languages_url"])
            language_totals.update(languages)
        except Exception as exc:
            print(f"Skipping language data for {repo.get('name')}: {exc}")

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    variables = {
        "login": USERNAME,
        "from": f"{since.isoformat()}T00:00:00Z",
        "to": f"{today.isoformat()}T23:59:59Z",
    }
    result = get_json("https://api.github.com/graphql", {"query": query, "variables": variables})
    if result.get("errors"):
        raise RuntimeError("GitHub contribution query failed: " + json.dumps(result["errors"]))
    calendar = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [
        (date.fromisoformat(day["date"]), day["contributionCount"])
        for week in calendar["weeks"] for day in week["contributionDays"]
    ]
    active = [day for day in days if day[1] > 0]
    current_streak = 0
    day_map = dict(days)
    cursor = today if day_map.get(today, 0) > 0 else today - timedelta(days=1)
    while day_map.get(cursor, 0) > 0:
        current_streak += 1
        cursor -= timedelta(days=1)
    longest = run = 0
    previous = None
    for day, count in days:
        if count:
            run = run + 1 if previous == day - timedelta(days=1) else 1
            longest = max(longest, run)
            previous = day
        else:
            run = 0
            previous = None

    stats_body = (
        metric(32, 105, user.get("public_repos", 0), "Public repositories") +
        metric(270, 105, stars, "Stars earned") +
        metric(508, 105, forks, "Forks received") +
        metric(32, 190, calendar["totalContributions"], "Contributions · last 365 days") +
        metric(270, 190, user.get("followers", 0), "Followers") +
        metric(508, 190, user.get("following", 0), "Following")
    )
    Path("assets/github-stats.svg").write_text(svg_card("Amar's GitHub Overview", 740, 235, stats_body), encoding="utf-8")

    top = language_totals.most_common(6)
    total = sum(language_totals.values()) or 1
    palette = ["#3572A5", "#f1e05a", "#e34c26", "#563d7c", "#2b7489", "#4F5D95"]
    x = 28
    bar_y = 78
    bar_w = 684
    for index, (name, amount) in enumerate(top):
        segment = bar_w * amount / total
        stats_body = "" if not top else ""
        x += segment
    x = 28
    bars = ""
    for index, (name, amount) in enumerate(top):
        segment = bar_w * amount / total
        bars += f'<rect x="{x:.1f}" y="{bar_y}" width="{max(segment, 1):.1f}" height="13" rx="4" fill="{palette[index % len(palette)]}"/>'
        x += segment
    rows = ""
    for index, (name, amount) in enumerate(top):
        col = index // 3
        row = index % 3
        px = 32 + col * 350
        py = 132 + row * 31
        pct = amount / total * 100
        rows += f'<circle cx="{px}" cy="{py-5}" r="5" fill="{palette[index % len(palette)]}"/>'
        rows += f'<text x="{px+14}" y="{py}" fill="#e8eefc" font-family="Arial,sans-serif" font-size="14">{escape(name)} · {pct:.1f}%</text>'
    if not top:
        rows = '<text x="32" y="145" fill="#e8eefc" font-family="Arial,sans-serif" font-size="15">No public language data available yet.</text>'
    Path("assets/languages.svg").write_text(svg_card("Most Used Languages · Public Repositories", 740, 245, bars + rows), encoding="utf-8")

    streak_body = (
        metric(45, 125, calendar["totalContributions"], "Contributions · last 365 days") +
        metric(285, 125, current_streak, "Current streak · days") +
        metric(525, 125, longest, "Longest streak · last 365 days") +
        f'<text x="45" y="205" fill="#9eacc7" font-family="Arial,sans-serif" font-size="13">Contribution activity from {since.isoformat()} through {today.isoformat()}</text>'
    )
    Path("assets/contribution-streak.svg").write_text(svg_card("Contribution Activity", 740, 235, streak_body), encoding="utf-8")
    print(f"Updated profile stats for {USERNAME}: {len(repos)} public repositories, {calendar['totalContributions']} contributions in the last 365 days.")

if __name__ == "__main__":
    Path("assets").mkdir(exist_ok=True)
    main()
