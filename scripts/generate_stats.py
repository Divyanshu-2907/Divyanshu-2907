"""
Self-hosted GitHub stats card generator.
Fetches real stats via the GitHub API and renders a static SVG —
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

    featured_repo = max(repos, key=lambda r: r.get("stargazers_count", 0), default=None)
    
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
        "following": user.get("following", 0),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "top_langs": top_langs,
        "featured_repo_name": featured_repo.get("name") if featured_repo else "N/A",
        "featured_repo_stars": featured_repo.get("stargazers_count") if featured_repo else 0,
        "account_age_years": account_age_years,
        "total_commits_1y": total_commits_1y,
        "os_prs_merged": os_prs_merged,
        "streak": streak,
        "activity": activity,
    }


def render_svg(stats):
    y = 135
    
    stats_text = f"""
  <text x="20" y="30" fill="#39d353" font-size="16" font-weight="bold" font-family="Segoe UI, sans-serif">{stats['public_repos']} public repos &#183; {stats['followers']} followers</text>
  <text x="20" y="55" fill="#8b949e" font-size="13" font-family="Segoe UI, sans-serif">&#9733; {stats['total_stars']} stars earned &#183; {stats['total_forks']} forks</text>
  <text x="20" y="75" fill="#8b949e" font-size="13" font-family="Segoe UI, sans-serif">&#128187; {stats['total_commits_1y']} commits (last 12m) &#183; {stats['streak']} day streak</text>
  <text x="20" y="95" fill="#8b949e" font-size="13" font-family="Segoe UI, sans-serif">&#127775; Featured: {stats['featured_repo_name']} ({stats['featured_repo_stars']} stars)</text>
  <text x="20" y="115" fill="#8b949e" font-size="13" font-family="Segoe UI, sans-serif">&#127758; {stats['os_prs_merged']} OS PRs merged &#183; {stats['account_age_years']} years on GitHub</text>
  <line x1="20" y1="{y}" x2="400" y2="{y}" stroke="#30363d"/>
"""
    y += 25
    lang_rows = f'<text x="20" y="{y}" fill="#c9d1d9" font-size="13" font-weight="bold" font-family="Segoe UI, sans-serif">Top Languages</text>'
    y += 25
    
    max_count = max((c for _, c in stats["top_langs"]), default=1)
    for lang, count in stats["top_langs"]:
        bar_width = int(200 * (count / max_count))
        lang_rows += f"""
        <text x="20" y="{y}" fill="#c9d1d9" font-size="13" font-family="Segoe UI, sans-serif">{lang}</text>
        <rect x="120" y="{y - 12}" width="{bar_width}" height="10" rx="5" fill="#26a641"/>
        """
        y += 26

    y += 10
    activity_html = f'<text x="20" y="{y}" fill="#c9d1d9" font-size="13" font-weight="bold" font-family="Segoe UI, sans-serif">Activity (Last 14 days)</text>'
    y += 15
    
    activity = stats.get("activity", [0]*14)
    max_act = max(activity) if max(activity) > 0 else 1
    
    x_offset = 20
    for count in activity:
        height = max(4, int((count / max_act) * 30))
        y_pos = y + 30 - height
        
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
            
        activity_html += f'\n  <rect x="{x_offset}" y="{y_pos}" width="16" height="{height}" rx="3" fill="{color}"/>'
        x_offset += 20
        
    y += 45

    svg = f"""<svg width="420" height="{y}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" rx="10" fill="#0d1117" stroke="#30363d"/>
  {stats_text}
  {lang_rows}
  {activity_html}
</svg>"""
    return svg


if __name__ == "__main__":
    stats = fetch_stats()
    svg = render_svg(stats)
    os.makedirs("assets", exist_ok=True)
    with open("assets/stats-card.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("Wrote assets/stats-card.svg")
    print(stats)
