"""Radar de Ofertas: collect job candidates for the profile stored in the artifact.

Usage: python3 radar_search.py profile.json known_ids.json out.json

Sources: LinkedIn (via JobSpy, public listings, no login) and the public job-board
APIs of Greenhouse, Ashby and Lever for the companies in profile["boards"].
Output is a de-duplicated, normalized list that Claude scores against the profile.
"""
import hashlib, json, re, sys, time, warnings
from concurrent.futures import ThreadPoolExecutor
from html import unescape

import requests

warnings.filterwarnings("ignore")
UA = {"User-Agent": "RadarDeOfertas/1.0 (personal job search)"}
FX = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CAD": 0.73, "MXN": 0.055, "CLP": 0.00105, "BRL": 0.18}
PER_YEAR = {"yearly": 1, "year": 1, "annual": 1, "monthly": 12, "month": 12, "weekly": 52, "daily": 260, "hourly": 2080, "hour": 2080}


def jid(*parts):
    return hashlib.sha1("|".join(p.lower().strip() for p in parts if p).encode()).hexdigest()[:16]


def strip_html(s, n=1200):
    s = unescape(re.sub(r"<[^>]+>", " ", unescape(s or "")))
    return re.sub(r"\s+", " ", s).strip()[:n]


def money_from_text(text):
    """Find a '$150,000 - $200,000' / '$150K–$200K' style annual range in free text."""
    m = re.search(r"\$\s?(\d{2,3}(?:[,.]\d{3})+|\d{2,3}\s?[kK])\s*(?:-|–|—|to)\s*\$?\s?(\d{2,3}(?:[,.]\d{3})+|\d{2,3}\s?[kK])", text or "")
    if not m:
        return None, None
    def num(x):
        x = x.replace(" ", "")
        return int(x[:-1]) * 1000 if x[-1] in "kK" else int(re.sub(r"[,.]", "", x))
    lo, hi = num(m.group(1)), num(m.group(2))
    return (lo, hi) if 20000 <= lo <= hi <= 2000000 else (None, None)


def mode_of(*texts):
    t = " ".join(x or "" for x in texts).lower()
    if "hybrid" in t or "híbrido" in t:
        return "hybrid"
    if "remote" in t or "remoto" in t:
        return "remote"
    return "onsite"


def norm_salary(lo, hi, cur, interval):
    cur = (cur or "USD").upper()
    mult = PER_YEAR.get((interval or "yearly").lower(), 1)
    fx = FX.get(cur)
    lo = int(lo * mult) if lo else None
    hi = int(hi * mult) if hi else None
    return {
        "salaryMin": lo, "salaryMax": hi, "currency": cur,
        "salaryMinUSD": int(lo * fx) if lo and fx else None,
        "salaryMaxUSD": int(hi * fx) if hi and fx else None,
    }


def location_ok(loc, mode, profile):
    l = (loc or "").lower()
    cities = [c.lower() for c in profile.get("cities", [])]
    if mode == "remote" and "remote" in profile.get("modes", []):
        # Remote roles must be open to the US or LATAM, where the candidate can work.
        return not l or any(k in l for k in ["us", "united states", "america", "latam", "anywhere", "global", "remote", "florida"])
    return any(c.split(",")[0] in l for c in cities) and (mode in profile.get("modes", []))


def title_ok(title, profile):
    t = title.lower()
    if any(x.lower() in t for x in profile.get("titleExclude", [])):
        return False
    return any(re.search(k, t) for k in profile.get("titleKeywords", []))


# ---------- Sources ----------
LATAM_RE = r"latam|latin america|latinoam|south america|southern cone|chile|andean|hispanic|spanish[- ]speaking"
LEAD_RE = r"manager|director|head|lead|vp|vice president|principal|country|general manager|gm\b|banker|advisor|partner"


def linkedin_plan(profile):
    """(term, location, remote, kind) searches, user keywords and Chilean companies first.
    The list rotates daily so a long list is fully covered over a few days."""
    cities = profile.get("cities", []) or ["Miami"]
    plan = []
    for term in profile.get("searchKeywords", []):
        plan.append((term, "United States", True, "keyword"))
        plan += [(term, c, False, "keyword") for c in cities]
    for co in profile.get("chileCompanies", []):
        plan.append((co, "United States", False, "chile"))
    for term in profile.get("linkedinSearches", []):
        if "remote" in profile.get("modes", []):
            plan.append((term, "United States", True, "base"))
        plan += [(term, c, False, "base") for c in cities]
    if plan:
        k = time.gmtime().tm_yday % len(plan)
        plan = plan[k:] + plan[:k]
    return plan


GENERIC = {"the", "inc", "group", "and", "of", "de", "y", "sa", "s.a.", "corp", "company", "co"}


def company_matches(company, query):
    """True when every distinctive word of the searched company appears in the result's company."""
    words = [w for w in re.split(r"[^a-z0-9]+", query.lower()) if w and w not in GENERIC]
    c = company.lower()
    return bool(words) and all(w in c for w in words)


def from_linkedin(profile):
    from jobspy import scrape_jobs
    out = []
    deadline = time.time() + profile.get("linkedinBudgetSec", 420)
    for term, loc, remote, kind in linkedin_plan(profile):
        if time.time() > deadline:
            print("linkedin: time budget reached, the rest rotates in tomorrow", file=sys.stderr)
            break
        try:
            df = scrape_jobs(site_name=["linkedin"], search_term=term, location=loc, is_remote=remote,
                             results_wanted=profile.get("linkedinPerSearch", 15), hours_old=profile.get("hoursOld", 72),
                             linkedin_fetch_description=profile.get("linkedinFetchDescription", False), verbose=0)
        except Exception as e:  # rate limited or blocked: keep going with other sources
            print(f"linkedin '{term}' @ {loc}: {type(e).__name__}", file=sys.stderr)
            continue
        for r in df.fillna("").to_dict("records"):
            title, company = str(r.get("title", "")), str(r.get("company", ""))
            if kind == "chile" and not company_matches(company, term):
                continue  # LinkedIn returns loosely related companies for a company-name search
            loc_txt = str(r.get("location", ""))
            mode = "remote" if r.get("is_remote") is True else mode_of(loc_txt, title)
            sal = norm_salary(r.get("min_amount") or None, r.get("max_amount") or None, r.get("currency") or "USD", r.get("interval") or "yearly")
            desc = strip_html(str(r.get("description", "")))
            if not sal["salaryMin"]:
                lo, hi = money_from_text(desc)
                if lo:
                    sal = norm_salary(lo, hi, "USD", "yearly")
            out.append({"title": title, "company": company, "location": loc_txt, "mode": mode,
                        "url": str(r.get("job_url", "")), "postedAt": str(r.get("date_posted", "")),
                        "source": "LinkedIn", "description": desc, "query": term, "queryKind": kind,
                        "chileCompany": kind == "chile", **sal})
        time.sleep(1.5)
    return out


def from_greenhouse(slug, name):
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", headers=UA, timeout=20)
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        content = unescape(j.get("content", ""))
        lo, hi = money_from_text(strip_html(content, 20000))
        loc = (j.get("location") or {}).get("name", "")
        out.append({"title": j.get("title", ""), "company": name, "location": loc, "mode": mode_of(loc, j.get("title")),
                    "url": j.get("absolute_url", ""), "postedAt": j.get("updated_at", ""), "source": "Greenhouse",
                    "ats": {"type": "greenhouse", "slug": slug, "id": str(j.get("id"))},
                    "description": strip_html(content), **norm_salary(lo, hi, "USD", "yearly")})
    return out


def from_ashby(slug, name):
    r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true", headers=UA, timeout=20)
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        comp = j.get("compensation") or {}
        lo = hi = None
        cur = "USD"
        for tier in comp.get("summaryComponents", []) or []:
            if tier.get("compensationType") == "Salary":
                lo, hi, cur = tier.get("minValue"), tier.get("maxValue"), tier.get("currencyCode") or "USD"
                interval = (tier.get("interval") or "1 YEAR").lower()
                break
        else:
            interval = "yearly"
        loc = j.get("location", "")
        mode = "remote" if j.get("isRemote") else mode_of(loc, j.get("workplaceType"))
        out.append({"title": j.get("title", ""), "company": name, "location": loc, "mode": mode,
                    "url": j.get("jobUrl", ""), "postedAt": j.get("publishedAt", ""), "source": "Ashby",
                    "ats": {"type": "ashby", "slug": slug, "id": str(j.get("id"))},
                    "description": strip_html(j.get("descriptionPlain") or j.get("descriptionHtml", "")),
                    **norm_salary(lo, hi, cur, "hourly" if "hour" in interval else "yearly")})
    return out


def from_lever(slug, name):
    r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json", headers=UA, timeout=20)
    r.raise_for_status()
    out = []
    for j in r.json():
        cat = j.get("categories") or {}
        sr = j.get("salaryRange") or {}
        loc = cat.get("location", "")
        interval = "hourly" if "hour" in (sr.get("interval") or "").lower() else "yearly"
        out.append({"title": j.get("text", ""), "company": name, "location": loc,
                    "mode": "remote" if j.get("workplaceType") == "remote" else mode_of(loc, j.get("workplaceType")),
                    "url": j.get("hostedUrl", ""), "postedAt": time.strftime("%Y-%m-%d", time.gmtime((j.get("createdAt") or 0) / 1000)),
                    "source": "Lever", "description": strip_html(j.get("descriptionPlain", "")),
                    "ats": {"type": "lever", "slug": slug, "id": str(j.get("id"))},
                    **norm_salary(sr.get("min"), sr.get("max"), sr.get("currency") or "USD", interval)})
    return out


BOARD = {"greenhouse": from_greenhouse, "ashby": from_ashby, "lever": from_lever}


def from_email(path):
    """Jobs the daily agent read from email alerts (LinkedIn, Glassdoor, Indeed), already parsed to
    {title, company, location, url, source, salaryMin?, salaryMax?, salaryEstimated?}."""
    out = []
    for j in json.load(open(path)):
        loc = j.get("location", "")
        sal = norm_salary(j.get("salaryMin"), j.get("salaryMax"), j.get("currency") or "USD", "yearly")
        out.append({"title": j.get("title", ""), "company": j.get("company", ""), "location": loc,
                    "mode": j.get("mode") or mode_of(loc, j.get("title")), "url": j.get("url", ""),
                    "postedAt": j.get("postedAt", ""), "source": j.get("source", "Email alert"),
                    "description": j.get("description", ""), "queryKind": "email",
                    "salaryEstimated": bool(j.get("salaryEstimated")), **sal})
    return out


ATS_URL = [("greenhouse", r"(?:job-boards|boards)\.greenhouse\.io/([\w-]+)/jobs/(\d+)"),
           ("lever", r"jobs\.lever\.co/([\w.-]+)/([0-9a-f-]{36})"),
           ("ashby", r"jobs\.ashbyhq\.com/([\w.%-]+)/([0-9a-f-]{36})")]


def ats_from_url(url):
    for kind, rx in ATS_URL:
        m = re.search(rx, url or "")
        if m:
            return {"type": kind, "slug": m.group(1), "id": m.group(2)}
    return None


def main(profile_path, known_path, out_path, email_path=None):
    profile = json.load(open(profile_path))
    known = set(json.load(open(known_path))) if known_path else set()
    report, rows = {}, []

    def run_board(b):
        try:
            res = BOARD[b["ats"]](b["slug"], b["name"])
            return b, res, None
        except Exception as e:
            return b, [], f"{type(e).__name__}: {str(e)[:80]}"

    with ThreadPoolExecutor(8) as ex:
        for b, res, err in ex.map(run_board, profile.get("boards", [])):
            report[f'{b["ats"]}/{b["slug"]}'] = err or len(res)
            rows += res
    if email_path:
        em = from_email(email_path)
        report["email alerts"] = len(em)
        rows += em
    li = from_linkedin(profile)
    report["linkedin"] = len(li)
    rows += li

    seen, out = set(), []
    for r in rows:
        kind = r.get("queryKind", "base")
        t = r["title"].lower()
        if not r["title"] or any(x.lower() in t for x in profile.get("titleExclude", [])):
            continue
        if kind == "chile":
            relevant = title_ok(r["title"], profile) or re.search(LEAD_RE, t)
            # Chilean companies: any U.S. location; scoring weighs Miami vs relocation
            located = r["mode"] == "remote" or any(k in r["location"].lower() for k in ["united states", ", fl", "florida", "usa", ", ny", ", ca", ", tx", ", ga"])
        elif kind == "keyword":
            same_co = company_matches(r["company"], r.get("query", "").split()[0])
            relevant = title_ok(r["title"], profile) or re.search(LATAM_RE, t) or (same_co and re.search(LEAD_RE, t))
            located = location_ok(r["location"], r["mode"], profile)
        elif kind == "email":
            # Alerts are already targeted; only drop titles that are clearly off-profile
            relevant = title_ok(r["title"], profile) or re.search(LATAM_RE, t) or re.search(LEAD_RE, t)
            located = location_ok(r["location"], r["mode"], profile)
        else:
            relevant = title_ok(r["title"], profile) or re.search(LATAM_RE, t)
            located = location_ok(r["location"], r["mode"], profile)
        if not (relevant and located):
            continue
        r["id"] = jid(r["company"], r["title"], r["location"])
        if r["id"] in seen or r["id"] in known:
            continue
        ceil = r.get("salaryMaxUSD") or r.get("salaryMinUSD")
        if ceil and not r.get("salaryEstimated") and ceil < profile.get("salaryMinUSD", 0) * 0.85:
            continue  # clearly below the floor; keep near-misses for Claude to judge
        if not r.get("ats"):
            ats = ats_from_url(r.get("url"))
            if ats:
                r["ats"] = ats
        seen.add(r["id"])
        out.append(r)
    json.dump({"report": report, "candidates": out}, open(out_path, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(report, indent=1))
    print(f"{len(out)} candidatos nuevos")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None,
         sys.argv[3] if len(sys.argv) > 3 else "candidates.json", sys.argv[4] if len(sys.argv) > 4 else None)
