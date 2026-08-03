"""
Self-hosted GitHub stats card generator.
Fetches real stats via the GitHub API and renders static SVGs —
no dependency on any third-party Vercel instance.

Run in CI (GitHub Actions) with GITHUB_TOKEN provided automatically,
or locally with a personal access token exported as GH_TOKEN.
"""

import os
import requests
from datetime import datetime, timezone, timedelta

USERNAME = os.environ.get("GH_USERNAME", "Divyanshu-2907")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

HEADERS = {"Accept": "application/vnd.github.v3+json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

API = "https://api.github.com"

# Theme Colors
BG = "#0d1117"
BORDER = "#30363d"
GREEN = "#2ea043"
TEXT = "#8b949e"
TITLE = "#c9d1d9"


def get_json(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_streak_and_activity():
    page = 1
    today = datetime.now(timezone.utc).date()
    commit_dates = set()
    commit_counts_per_day = {}
    
    streak_found = False
    temp_streak = 0
    
    while page <= 10:
        url = f"{API}/search/commits?q=author:{USERNAME}&sort=author-date&order=desc&per_page=100&page={page}"
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            break
        data = r.json()
        items = data.get("items", [])
        if not items:
            break
            
        batch_dates = []
        for item in items:
            date_str = item["commit"]["author"]["date"]
            d = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(timezone.utc).date()
            commit_dates.add(d)
            batch_dates.append(d)
            commit_counts_per_day[d] = commit_counts_per_day.get(d, 0) + 1
            
        oldest_in_batch = min(batch_dates)
        
        if not streak_found:
            current = today
            t_streak = 0
            if current in commit_dates:
                t_streak += 1
                current -= timedelta(days=1)
            elif (current - timedelta(days=1)) in commit_dates:
                current -= timedelta(days=1)
                t_streak += 1
                current -= timedelta(days=1)
                
            while current in commit_dates:
                t_streak += 1
                current -= timedelta(days=1)
                
            if current >= oldest_in_batch:
                temp_streak = t_streak
                streak_found = True

        fourteen_days_ago = today - timedelta(days=14)
        if streak_found and oldest_in_batch <= fourteen_days_ago:
            break
            
        if len(items) < 100:
            break
        page += 1
        
    if not streak_found:
        current = today
        t_streak = 0
        if current in commit_dates:
            t_streak += 1
            current -= timedelta(days=1)
        elif (current - timedelta(days=1)) in commit_dates:
            current -= timedelta(days=1)
            t_streak += 1
            current -= timedelta(days=1)
            
        while current in commit_dates:
            t_streak += 1
            current -= timedelta(days=1)
        temp_streak = t_streak

    activity = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        activity.append(commit_counts_per_day.get(d, 0))
        
    return temp_streak, activity


def fetch_stats():
    user = get_json(f"{API}/users/{USERNAME}")
    repos = get_json(f"{API}/users/{USERNAME}/repos?per_page=100&type=owner")

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)

    featured_repos = []
    for name in ["Hexapod_Robot", "CodeQuest-AI", "Hexmind"]:
        repo = next((r for r in repos if r.get("name") == name), None)
        if repo:
            featured_repos.append(repo)
    if not featured_repos:
        top = max(repos, key=lambda r: r.get("stargazers_count", 0), default=None)
        if top: featured_repos.append(top)
    
    created_at_str = user.get("created_at")
    account_age_years = 0
    if created_at_str:
        created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        account_age_years = (datetime.now(timezone.utc) - created_at).days // 365

    lang_counts = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
    top_langs = sorted(lang_counts.items(), key=lambda x: -x[1])[:5]

    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    commits_url = f"{API}/search/commits?q=author:{USERNAME}+committer-date:>{one_year_ago}"
    total_commits_1y = 0
    try:
        total_commits_1y = get_json(commits_url).get("total_count", 0)
    except Exception:
        pass

    prs_url = f"{API}/search/issues?q=type:pr+is:merged+author:{USERNAME}+-user:{USERNAME}"
    os_prs_merged = 0
    try:
        os_prs_merged = get_json(prs_url).get("total_count", 0)
    except Exception:
        pass

    streak, activity = get_streak_and_activity()

    return {
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "top_langs": top_langs,
        "featured_repos": featured_repos,
        "account_age_years": account_age_years,
        "total_commits_1y": total_commits_1y,
        "os_prs_merged": os_prs_merged,
        "streak": streak,
        "activity": activity,
    }

def base_svg(title, content, height):
    return f"""<svg width="400" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" rx="10" fill="{BG}" stroke="{BORDER}"/>
  <text x="20" y="30" fill="{GREEN}" font-size="16" font-weight="bold" font-family="Segoe UI, sans-serif">{title}</text>
  {content}
</svg>"""

def render_overview(stats):
    content = f"""
  <text x="20" y="60" fill="{TEXT}" font-size="14" font-family="Segoe UI, sans-serif">&#128187; {stats['public_repos']} public repos</text>
  <text x="20" y="85" fill="{TEXT}" font-size="14" font-family="Segoe UI, sans-serif">&#128101; {stats['followers']} followers</text>
  <text x="20" y="110" fill="{TEXT}" font-size="14" font-family="Segoe UI, sans-serif">&#9733; {stats['total_stars']} stars earned</text>
  <text x="20" y="135" fill="{TEXT}" font-size="14" font-family="Segoe UI, sans-serif">&#127758; {stats['os_prs_merged']} OS PRs merged</text>
  <text x="20" y="160" fill="{TEXT}" font-size="14" font-family="Segoe UI, sans-serif">&#8986; {stats['account_age_years']} years on GitHub</text>
"""
    return base_svg("Overview", content, 185)

def render_streak(stats):
    content = f"""
  <text x="20" y="60" fill="{TEXT}" font-size="14" font-family="Segoe UI, sans-serif">&#128293; Current Streak: <tspan fill="{TITLE}" font-weight="bold">{stats['streak']} days</tspan></text>
  <text x="20" y="85" fill="{TEXT}" font-size="14" font-family="Segoe UI, sans-serif">&#128221; Total Commits (1yr): <tspan fill="{TITLE}" font-weight="bold">{stats['total_commits_1y']}</tspan></text>
  <text x="20" y="125" fill="{GREEN}" font-size="13" font-weight="bold" font-family="Segoe UI, sans-serif">Hardcore Projects</text>
"""
    y = 150
    for repo in stats.get('featured_repos', []):
        name = repo.get("name", "Unknown")
        lang = repo.get("language") or "Code"
        content += f'  <text x="20" y="{y}" fill="{TEXT}" font-size="13" font-family="Segoe UI, sans-serif">&#127775; <tspan fill="{TITLE}">{name}</tspan> <tspan fill="{TEXT}" font-size="11">({lang})</tspan></text>\n'
        y += 22

    return base_svg("Contributions & Projects", content, 185 if y <= 185 else y + 10)

def render_languages(stats):
    content = ""
    y = 60
    max_count = max((c for _, c in stats["top_langs"]), default=1)
    for lang, count in stats["top_langs"]:
        bar_width = int(220 * (count / max_count))
        content += f"""
  <text x="20" y="{y}" fill="{TITLE}" font-size="13" font-family="Segoe UI, sans-serif">{lang}</text>
  <rect x="130" y="{y - 12}" width="{bar_width}" height="10" rx="5" fill="#2ea043"/>
"""
        y += 28
    return base_svg("Top Languages", content, y + 10)

def render_activity(stats):
    content = ""
    activity = stats.get("activity", [0]*14)
    max_act = max(activity) if max(activity) > 0 else 1
    
    x_offset = 20
    for count in activity:
        height = max(4, int((count / max_act) * 80))
        y_pos = 140 - height
        
        if count == 0:
            color = "#161b22"
        elif count <= max_act * 0.25:
            color = "#0e4429"
        elif count <= max_act * 0.5:
            color = "#006d32"
        elif count <= max_act * 0.75:
            color = "#26a641"
        else:
            color = "#39d353"
            
        content += f'\n  <rect x="{x_offset}" y="{y_pos}" width="20" height="{height}" rx="3" fill="{color}"/>'
        x_offset += 26
    
    content += f'\n  <text x="20" y="165" fill="{TEXT}" font-size="12" font-family="Segoe UI, sans-serif">Commit activity over the last 14 days</text>'
    return base_svg("Recent Activity", content, 185)

if __name__ == "__main__":
    stats = fetch_stats()
    
    os.makedirs("assets", exist_ok=True)
    
    files = {
        "assets/overview.svg": render_overview(stats),
        "assets/streak.svg": render_streak(stats),
        "assets/languages.svg": render_languages(stats),
        "assets/activity.svg": render_activity(stats),
    }
    
    for filename, content in files.items():
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Wrote {filename}")
    
    print(stats)
