from concurrent.futures import ThreadPoolExecutor
from core.utils import make_request, domain_of
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re
import time
import random
from typing import Dict, Any  # ¡IMPORTANTE: importar Dict y Any!

# Esto es necesario para la extracción posterior
try:
    from core.extractors import extract_all
except ImportError:
    extract_all = None

SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
    "yandex": "https://yandex.com/search/?text={query}",
    "baidu": "https://www.baidu.com/s?wd={query}"
}

SOCIAL_SITES = [
    "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com",
    "github.com", "linkedin.com"
]

REPO_SITES = [
    "pastebin.com", "mediafire.com", "mega.nz", "drive.google.com", "github.com"
]

def delay_random(min_delay=0.8, max_delay=2.5):
    """Espera un tiempo aleatorio para parecer más humano."""
    time.sleep(random.uniform(min_delay, max_delay))

class SiteSearcher:
    """Clase unificada de búsqueda OSINT."""
    
    def __init__(self, client_headers=None, timeout=12, proxy=None, limiter=None, cache=None):
        """Constructor sin parámetro 'limit' (se pasa en unified_search)"""
        self.client_headers = client_headers
        self.timeout = timeout
        self.proxy = proxy
        self.limiter = limiter
        self.cache = cache

    def _extract_results_from_html(self, text, engine_name):
        """Extrae resultados específicos según el motor de búsqueda."""
        if not text:
            return []
            
        soup = BeautifulSoup(text, "html.parser")
        results = []
        
        if engine_name == "google":
            # Selectores para Google
            for div in soup.select('div.g, div.tF2Cxc'):
                a = div.find('a', href=True)
                if a and a['href'].startswith('http'):
                    title = div.select_one('h3') or div.select_one('div[role="heading"]')
                    snippet = div.select_one('div.VwiC3b, span.aCOpRe')
                    results.append({
                        "engine": "google",
                        "title": title.get_text().strip() if title else "",
                        "link": a['href'],
                        "snippet": snippet.get_text().strip()[:200] if snippet else ""
                    })
        elif engine_name == "bing":
            # Selectores para Bing
            for li in soup.select('li.b_algo'):
                a = li.find('a', href=True)
                if a and a['href'].startswith('http'):
                    title = li.select_one('h2') or li.select_one('a')
                    snippet = li.select_one('p')
                    results.append({
                        "engine": "bing",
                        "title": title.get_text().strip() if title else "",
                        "link": a['href'],
                        "snippet": snippet.get_text().strip()[:200] if snippet else ""
                    })
        # Método fallback para otros motores
        else:
            for a in soup.find_all('a', href=True):
                if a['href'].startswith('http') and not any(ex in a['href'] for ex in ["google.com", "bing.com", "yandex.com", "baidu.com"]):
                    title = a.get_text().strip()
                    if len(title) > 5:  # evitar textos muy cortos
                        results.append({
                            "engine": engine_name,
                            "title": title[:100],
                            "link": a['href'],
                            "snippet": ""
                        })
        
        return results

    def search_engines(self, query, limit=6):
        """Realiza búsqueda en motores específicos con límite de resultados."""
        results = []
        query_encoded = quote_plus(query)
        
        for name, url_template in SEARCH_ENGINES.items():
            if len(results) >= limit:
                break
                
            qurl = url_template.format(query=query_encoded)
            status, html = make_request(
                qurl, 
                limiter=self.limiter, 
                cache=self.cache,
                headers=self.client_headers, 
                timeout=self.timeout,
                proxy=self.proxy
            )
            
            if status == 200 and html:
                engine_results = self._extract_results_from_html(html, name)
                # Filtrar dominios de los motores de búsqueda
                filtered = [r for r in engine_results 
                           if domain_of(r['link']) not in ["google.com", "bing.com", "yandex.com", "baidu.com"]]
                results.extend(filtered[:limit - len(results)])
                
            delay_random()
            
        return results[:limit]

    def search_socials(self, name, limit=4):
        """Búsqueda específica en redes sociales."""
        results = []
        for site in SOCIAL_SITES:
            if len(results) >= limit:
                break
            q = f'"{name}" site:{site}'
            social_results = self.search_engines(q, limit=2)
            results.extend(social_results)
        return results[:limit]

    def search_repositories(self, name, limit=3):
        """Búsqueda en repositorios y plataformas de archivos."""
        results = []
        for site in REPO_SITES:
            if len(results) >= limit:
                break
            q = f'"{name}" site:{site}'
            repo_results = self.search_engines(q, limit=2)
            results.extend(repo_results)
        return results[:limit]

    def unified_search(self, name, limit=10, include_socials=True, include_repos=True) -> Dict[str, Any]:
        """Búsqueda unificada con parámetros correctos."""
        all_results = []
        content_for_extraction = f"{name}\n"
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self.search_engines, name, limit)]
            if include_socials:
                futures.append(executor.submit(self.search_socials, name, max(1, limit//3)))
            if include_repos:
                futures.append(executor.submit(self.search_repositories, name, max(1, limit//4)))
                
            for future in futures:
                try:
                    all_results.extend(future.result())
                except Exception as e:
                    print(f"Error en búsqueda paralela: {e}")
        
        # Eliminar duplicados manteniendo el orden
        seen_urls = set()
        clean_results = []
        for r in all_results:
            url = r.get('link') or r.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                clean_results.append(r)
                content_for_extraction += f"{r.get('title', '')} {r.get('snippet', '')} {url}\n"
        
        clean_results = clean_results[:limit]
        
        # Extracción de entidades
        entities = {}
        if extract_all:
            try:
                extracted = extract_all(content_for_extraction)
                # Procesar correctamente el formato de perfiles sociales
                if extracted.get("social_profiles"):
                    entities["socials"] = extracted["social_profiles"]  # Ya tiene formato correcto
                # Incluir otros campos relevantes
                for key in ["emails", "phones", "links", "usernames", "names"]:
                    if extracted.get(key):
                        entities[key] = extracted[key]
            except Exception as e:
                print(f"Error en extracción de entidades: {e}")
        
        return {
            "query": name,
            "results": clean_results,
            "entities": entities,
            "count": len(clean_results)
        }

if __name__ == '__main__':
    print("Módulo SiteSearcher cargado. Ejecuta main.py o gui.py para usar la herramienta.")