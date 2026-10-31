"""Render a resume JSON (the shape of the dashboard's config/resume) to HTML and PDF.

Usage: python3 render_resume.py resume.json "Raffaello Criscuoli - Resume.pdf"

Uses resume.css and the IBM Plex fonts in ./fonts (embedded, so the PDF looks the same on any machine).
PDF printing uses headless Chrome/Chromium: set CHROME_PATH, or it tries the usual install locations.
"""
import base64, html, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = [("IBM Plex Sans", 400, "normal", "ibm-plex-sans-latin-400-normal.woff2"),
         ("IBM Plex Sans", 400, "italic", "ibm-plex-sans-latin-400-italic.woff2"),
         ("IBM Plex Sans", 500, "normal", "ibm-plex-sans-latin-500-normal.woff2"),
         ("IBM Plex Sans", 600, "normal", "ibm-plex-sans-latin-600-normal.woff2"),
         ("IBM Plex Sans", 700, "normal", "ibm-plex-sans-latin-700-normal.woff2"),
         ("IBM Plex Mono", 400, "normal", "ibm-plex-mono-latin-400-normal.woff2"),
         ("IBM Plex Mono", 500, "normal", "ibm-plex-mono-latin-500-normal.woff2")]
CHROMES = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
           "/Applications/Chromium.app/Contents/MacOS/Chromium",
           "google-chrome", "chromium", "chromium-browser", "/opt/pw-browsers/chromium"]
e = html.escape


def font_faces():
    out = []
    for fam, weight, style, f in FONTS:
        p = HERE / "fonts" / f
        if p.exists():
            data = base64.b64encode(p.read_bytes()).decode()
            out.append(f'@font-face{{font-family:"{fam}";font-weight:{weight};font-style:{style};'
                       f'src:url(data:font/woff2;base64,{data}) format("woff2");}}')
    return "\n".join(out)


def build_html(r):
    contact = [r.get("location"), r.get("phone"), r.get("email"), r.get("linkedin")]
    roles = "".join(
        f'<div class="role"><div class="role-head"><div><span class="role-title">{e(x["title"])}</span>'
        f' <span class="role-org">· {e(x["company"])}</span></div>'
        f'<div class="role-meta">{e(x["dates"])}{" · " + e(x["location"]) if x.get("location") else ""}</div></div>'
        f'<ul>{"".join(f"<li>{e(b)}</li>" for b in x.get("bullets", []))}</ul></div>'
        for x in r.get("experience", []))
    projects = "".join(f'<div class="project"><b>{e(p["name"])}</b> — {e(p["text"])}</div>' for p in r.get("projects", []))
    skills = "".join(
        f'<div class="k">{e(k)}</div><div class="chips">{"".join(f"<span class=chip>{e(s)}</span>" for s in v)}</div>'
        for k, v in r.get("skills", {}).items())
    edu = "".join(f'<div><span class="k">Education</span><span class="v">{e(x["degree"])}</span><br>{e(x["school"])} · {e(x["dates"])}</div>'
                  for x in r.get("education", []))
    creds = (f'<div><span class="k">Licenses &amp; languages</span><span class="v">{e(", ".join(r.get("licenses", [])))}</span><br>'
             f'{e(", ".join(r.get("languages", [])))} · {e(r.get("citizenship", "U.S. & Chilean citizen"))}</div>')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{e(r["name"])} — Resume</title>
<style>{font_faces()}
{(HERE / "resume.css").read_text()}</style></head>
<body class="{"compact" if r.get("onePage") else ""}">
<header>
  <h1>{e(r["name"])}</h1>
  <div class="headline">{e(r.get("headline", ""))}</div>
  <div class="contact">{"".join(f"<span>{e(c)}</span>" for c in contact if c)}</div>
</header>
<h2>Summary</h2><p class="summary">{e(r.get("summary", ""))}</p>
<h2>Experience</h2>{roles}
{f"<h2>Selected projects</h2>{projects}" if projects else ""}
<h2>Skills</h2><div class="skills">{skills}</div>
<h2>Education &amp; credentials</h2><div class="facts">{edu}{creds}</div>
</body></html>'''


def find_chrome():
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]
    for c in CHROMES:
        if os.path.isabs(c) and os.path.exists(c):
            return c
        if not os.path.isabs(c) and shutil.which(c):
            return shutil.which(c)
    return None


def main(src, pdf_path):
    r = json.load(open(src))
    pdf = Path(pdf_path).resolve()
    html_path = pdf.with_suffix(".html")
    html_path.write_text(build_html(r), encoding="utf-8")
    chrome = find_chrome()
    if not chrome:
        sys.exit(f"Wrote {html_path}. No Chrome found to print the PDF; set CHROME_PATH.")
    subprocess.run([chrome, "--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", html_path.as_uri()], check=True, capture_output=True)
    print(f"Wrote {pdf}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
