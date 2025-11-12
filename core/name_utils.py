# core/name_utils.py
import re
import unicodedata
from typing import List

def normalize_name(s: str) -> str:
    """Normaliza un nombre: elimina acentos, convierte a minúsculas y quita espacios extra."""
    if not isinstance(s, str):
        return ""
    s = s.strip()
    # Eliminar acentos
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("M"))
    # Unificar espacios y minúsculas
    s = re.sub(r"\s+", " ", s)
    return s.lower()

def name_variants_improved(fullname: str) -> List[str]:
    """
    Genera variaciones de un nombre completo para búsqueda OSINT.
    Crea combinaciones entre nombres y apellidos en diferentes órdenes.
    """
    s = normalize_name(fullname)
    if not s:
        return []

    parts = [p for p in s.split(" ") if p]
    variants = []
    username_set = set()

    def add_username_forms(first, second=None, last=None):
        """Crea posibles formas de usuario a partir de nombres y apellidos."""
        candidates = []
        if first and last:
            candidates += [
                f"{first}.{last}", f"{first}_{last}", f"{first}{last}",
                f"{first[0]}{last}", f"{first}{last[0]}", f"{first}-{last}", f"{last}.{first}"
            ]
            candidates += [f"{first[0]}.{last}", f"{first[0]}{last}"]
            if second:
                candidates += [f"{first[0]}{second[0]}{last}", f"{first[0]}.{second[0]}.{last}"]
        if first and second:
            candidates += [f"{first}.{second}", f"{first}_{second}", f"{first}{second}", f"{first[0]}{second}"]
        if first:
            candidates.append(first)
            candidates.append(f"{first[0]}{first}")

        for c in candidates:
            c2 = re.sub(r'[^a-z0-9._\-]', '', c.lower())
            if c2:
                username_set.add(c2)

    # Casos según cantidad de partes
    if len(parts) >= 4:
        first, second = parts[0], parts[1]
        surname1, surname2 = parts[-2], parts[-1]
        variants += [
            f"{first} {surname1} {surname2}",
            f"{second} {surname1} {surname2}",
            f"{surname1} {surname2} {first} {second}",
            f"{first} {second} {surname1}",
            f"{first} {second} {surname2}",
            f"{first} {surname1}",
            f"{first} {surname2}",
            f"{second} {surname1}",
            f"{second} {surname2}",
        ]
        variants += [f"{first} {second}", f"{surname1} {surname2}", f"{surname2} {surname1}"]
        add_username_forms(first, second, surname1)
        add_username_forms(first, second, surname2)
        add_username_forms(first, None, surname1)
        add_username_forms(second, None, surname1)

    elif len(parts) == 3:
        first, surname1, surname2 = parts[0], parts[1], parts[2]
        variants += [
            f"{surname1} {surname2} {first}",
            f"{first} {surname1} {surname2}",
            f"{first} {surname2}",
            f"{first} {surname1}",
            f"{surname1} {first}",
            f"{surname2} {first}",
        ]
        add_username_forms(first, None, surname1)
        add_username_forms(first, None, surname2)
        add_username_forms(first, None, None)

    elif len(parts) == 2:
        first, surname = parts[0], parts[1]
        variants += [f"{first} {surname}", f"{surname} {first}", first, surname]
        add_username_forms(first, None, surname)
        add_username_forms(first, None, None)

    else:
        variants.append(parts[0])
        add_username_forms(parts[0], None, None)

    # Eliminar duplicados y ordenar
    username_list = sorted(username_set, key=lambda x: (len(x), x))
    seen = set()
    out = []
    for v in variants:
        v2 = re.sub(r"\s+", " ", v).strip()
        if v2 and v2 not in seen:
            seen.add(v2)
            out.append(v2)
    for u in username_list:
        if u not in seen:
            out.append(u)
            seen.add(u)
    return out

def email_variants_from_name(fullname: str, domain_hints=None, max_per_domain=6) -> List[str]:
    """
    Genera posibles correos electrónicos a partir de un nombre.
    Ejemplo: Juan Pérez -> juan.perez@gmail.com, jperez@hotmail.com, etc.
    """
    domains = list(domain_hints or []) + ["gmail.com", "hotmail.com", "yahoo.com", "outlook.com", "live.com"]
    names = name_variants_improved(fullname)
    username_candidates = [n for n in names if " " not in n][:max_per_domain]
    extra = set()
    parts = normalize_name(fullname).split()
    if parts:
        first = parts[0]
        last = parts[-1] if len(parts) > 1 else ""
        if first and last:
            extra.update([f"{first}.{last}", f"{first}{last}", f"{first[0]}{last}", f"{first}_{last}"])
    username_candidates = list(dict.fromkeys(username_candidates + sorted(extra)))

    emails = []
    for dom in domains:
        count = 0
        for user in username_candidates:
            if count >= max_per_domain:
                break
            user_clean = re.sub(r'[^a-z0-9._\-]', '', user.lower())
            if not user_clean:
                continue
            emails.append(f"{user_clean}@{dom}")
            count += 1

    seen = set()
    out = []
    for e in emails:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out
