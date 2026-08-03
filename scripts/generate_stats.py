"""
Self-hosted GitHub stats card generator.
Fetches real stats via the GitHub API and renders a static SVG —
no dependency on any third-party Vercel instance.

Run in CI (GitHub Actions) with GITHUB_TOKEN provided automatically,
or locally with a personal access token exported as GH_TOKEN.
"""

import os
import requests

USERNAME = os.environ.get("GH_USERNAME", "Divyanshu-2907")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
API = "https://api.github.com"


def get_json(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def fetch_stats():
    user = get_json(f"{API}/users/{USERNAME}")
    repos = get_json(f"{API}/users/{USERNAME}/repos?per_page=100&type=owner")

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)

    # Language breakdown by repo count (simple, no extra API calls per repo)
    lang_counts = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
    top_langs = sorted(lang_counts.items(), key=lambda x: -x[1])[:5]

    return {
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "top_langs": top_langs,
    }


def render_svg(stats):
    lang_rows = ""
    y = 150
    max_count = max((c for _, c in stats["top_langs"]), default=1)
    for lang, count in stats["top_langs"]:
        bar_width = int(200 * (count / max_count))
        lang_rows += f"""
        <text x="20" y="{y}" fill="#c9d1d9" font-size="13" font-family="Segoe UI, sans-serif">{lang}</text>
        <rect x="120" y="{y - 12}" width="{bar_width}" height="10" rx="5" fill="#58a6ff"/>
        """
        y += 26

    svg = f"""<svg width="380" height="{y + 20}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" rx="10" fill="#0d1117" stroke="#30363d"/>
  <text x="20" y="30" fill="#58a6ff" font-size="16" font-weight="bold" font-family="Segoe UI, sans-serif">{stats['public_repos']} public repos &#183; {stats['followers']} followers</text>
  <text x="20" y="55" fill="#8b949e" font-size="13" font-family="Segoe UI, sans-serif">&#9733; {stats['total_stars']} stars earned &#183; {stats['total_forks']} forks</text>
  <line x1="20" y1="75" x2="360" y2="75" stroke="#30363d"/>
  <text x="20" y="100" fill="#c9d1d9" font-size="13" font-weight="bold" font-family="Segoe UI, sans-serif">Top Languages</text>
  {lang_rows}
</svg>"""
    return svg


if __name__ == "__main__":
    stats = fetch_stats()
    svg = render_svg(stats)
    os.makedirs("assets", exist_ok=True)
    with open("assets/stats-card.svg", "w") as f:
        f.write(svg)
    print("Wrote assets/stats-card.svg")
    print(stats)
