# core/site.py

from concurrent.futures import ThreadPoolExecutor
from core.utils import make_request, delay_random
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re

# ------------------------------------
# 1. Motores de búsqueda públicos
# ------------------------------------
SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
    "yandex": "https://yandex.com/search/?text={query}",
    "baidu": "https://www.baidu.com/s?wd={query}"
}

def search_engines(query, limit=10):
    results = []
    for name, url in SEARCH_ENGINES.items():
        qurl = url.format(query=quote_plus(query))
        html = make_request(qurl)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http"):
                    results.append({"engine": name, "url": href})
        delay_random()
    return results

# ------------------------------------
# 2. Redes sociales
# ------------------------------------
SOCIAL_SITES = [
    "facebook.com", "instagram.com", "twitter.com", "tiktok.com",
    "github.com", "linkedin.com"
]

def search_socials(name):
    results = []
    for site in SOCIAL_SITES:
        q = f'{name} site:{site}'
        results += search_engines(q)
    return results

# ------------------------------------
# 3. Repositorios públicos
# ------------------------------------
REPO_SITES = [
    "pastebin.com", "mediafire.com", "mega.nz", "drive.google.com", "github.com"
]

def search_repositories(name):
    results = []
    for site in REPO_SITES:
        q = f'{name} site:{site}'
        results += search_engines(q)
    return results

# ------------------------------------
# 4. Búsqueda unificada
# ------------------------------------
def search_all_sources(name, include_socials=True, include_repos=True):
    """
    Ejecuta búsqueda OSINT completa en motores, redes y repositorios.
    """
    all_results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        futures.append(executor.submit(search_engines, name))
        if include_socials:
            futures.append(executor.submit(search_socials, name))
        if include_repos:
            futures.append(executor.submit(search_repositories, name))
        for f in futures:
            all_results += f.result()
    # eliminar duplicados
    seen = set()
    clean = []
    for r in all_results:
        if r["url"] not in seen:
            seen.add(r["url"])
            clean.append(r)
    return clean
