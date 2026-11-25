"""Approval page for one video, and applying what you decided on it.

    python3 pipeline/review.py page  videos/001-...    # writes videos/001-.../review.html
    python3 pipeline/review.py serve videos/001-...    # opens it on your phone over Wi-Fi
    python3 pipeline/review.py apply videos/001-...    # reads review.json, redoes rejected scenes

On the page, every scene has three buttons: Approve, Redo (the AI tries again, with your note
added to the prompt) and Replace (you will drop in your own image). At the bottom you approve the
title, description and thumbnail and pick a publish time. "Save decisions" downloads
review.json; put it in the video folder (on the laptop it saves straight there when you use
`serve`).
"""
import html
import http.server
import json
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

CSS = """
:root{--bg:#0d1326;--card:#161f3a;--ink:#e9ecf5;--mute:#9aa3bd;--gold:#d4af37;--ok:#2e9e6b;--bad:#c0392b;--line:#26304f}
@media (prefers-color-scheme: light){:root{--bg:#f4f1ea;--card:#fff;--ink:#1d2333;--mute:#5b6375;--line:#e2ddd0}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:8px 0}h2{font-size:18px;margin:28px 0 8px;color:var(--gold)}
.meta{color:var(--mute);font-size:14px}
.scene{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:14px 0;overflow:hidden;display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr)}
@media (max-width:700px){.scene{grid-template-columns:1fr}}
.scene img{width:100%;height:100%;object-fit:cover;display:block;background:#000}
.body{padding:12px 14px}.id{font-weight:700}.tag{display:inline-block;font-size:12px;padding:1px 8px;border-radius:99px;border:1px solid var(--line);color:var(--mute);margin-left:6px}
.warn{color:#e67e22;font-size:13px;margin:6px 0}.vo{margin:8px 0}.prompt{color:var(--mute);font-size:13px}
.src{color:var(--gold);font-size:13px}
.btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
button{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid var(--line);background:transparent;color:var(--ink);cursor:pointer}
button.on.approve{background:var(--ok);border-color:var(--ok);color:#fff}
button.on.redo,button.on.replace{background:var(--bad);border-color:var(--bad);color:#fff}
textarea,input,select{width:100%;font:inherit;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);margin-top:8px}
video{width:100%;border-radius:12px;background:#000}
.bar{position:sticky;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.primary{background:var(--gold);border-color:var(--gold);color:#111;font-weight:700}
"""

JS = r"""
const KEY='review:'+DATA.folder; let st={};
try{st=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
st.scenes=st.scenes||{}; st.publish=st.publish||{};
function save(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){} count()}
function count(){const n=DATA.scenes.length, a=Object.values(st.scenes).filter(x=>x.decision==='approve').length;
 document.getElementById('count').textContent=a+' of '+n+' scenes approved'}
function pick(id,d){st.scenes[id]=st.scenes[id]||{}; st.scenes[id].decision=d; paint(id); save()}
function note(id,v){st.scenes[id]=st.scenes[id]||{}; st.scenes[id].note=v; save()}
function paint(id){const d=(st.scenes[id]||{}).decision; document.querySelectorAll('[data-s="'+id+'"]').forEach(b=>b.classList.toggle('on',b.dataset.d===d))}
function setp(k,v){st.publish[k]=v; save()}
async function out(){const body=JSON.stringify(st,null,1);
 try{const r=await fetch('review.json',{method:'PUT',body}); if(r.ok){alert('Saved to the video folder.');return}}catch(e){}
 const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([body],{type:'application/json'}));
 a.download='review.json'; a.click()}
window.addEventListener('DOMContentLoaded',()=>{DATA.scenes.forEach(s=>{paint(s.id); const t=document.getElementById('n_'+s.id); if(t) t.value=(st.scenes[s.id]||{}).note||''});
 for(const k of ['title','description','thumbnail','when','platforms']){const el=document.getElementById('p_'+k); if(el && st.publish[k]!==undefined){ if(el.type==='checkbox') el.checked=st.publish[k]; else el.value=st.publish[k]}}
 count()})
"""


def esc(s):
    return html.escape(str(s or ""))


def rel(folder, p):
    try:
        return os.path.relpath(p, folder)
    except ValueError:
        return p


def page(folder):
    folder = Path(folder)
    data = json.loads((folder / "scenes.json").read_text())
    meta = data["meta"]
    md = folder / "out" / "metadata.json"
    if md.exists():
        meta = {**meta, **json.loads(md.read_text())}
    scenes = data["scenes"]
    out = [f"<!doctype html><html lang=en><head><meta charset=utf-8>"
           f"<meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>Review: {esc(meta['title'])}</title><style>{CSS}</style></head><body><main>",
           f"<h1>{esc(meta['title'])}</h1><div class=meta>{esc(meta.get('series'))} · "
           f"{len(scenes)} scenes</div>"]
    if (folder / "out" / "long.mp4").exists():
        out.append("<h2>Full video</h2><video controls preload=metadata src='out/long.mp4'></video>")
    out.append("<h2>Scenes</h2><p class=meta>Approve each picture, or ask for a redo (add a note "
               "saying what to change), or mark it to replace with your own image.</p>")
    for s in scenes:
        img = rel(folder, s.get("image", "")) if s.get("image") else ""
        warn = ""
        if "face is fully covered" in s.get("prompt", "") or "entire face" in s.get("prompt", ""):
            warn = "<div class=warn>Check: a Prophet or Companion may appear. The face must be fully covered by light.</div>"
        if s.get("image_source") == "placeholder":
            warn += "<div class=warn>No picture yet (placeholder).</div>"
        cards = "".join(f"<div class=src>SOURCE: {esc(c)}</div>" for c in s.get("cards", []))
        t = f"{s['start']:.0f}s" if "start" in s else ""
        out.append(
            f"<div class=scene><img loading=lazy src='{esc(img)}' alt='{esc(s['visual'])}'>"
            f"<div class=body><span class=id>{esc(s['id'])}</span>"
            f"<span class=tag>{esc(s.get('image_source',''))}</span><span class=tag>{t}</span>"
            f"{warn}<div class=vo>{esc(s['vo']) or '<i>(no voice over this picture)</i>'}</div>{cards}"
            f"<div class=prompt>Picture: {esc(s['visual'])}</div>"
            f"<div class=btns>"
            f"<button class=approve data-s='{s['id']}' data-d=approve onclick=\"pick('{s['id']}','approve')\">Approve</button>"
            f"<button class=redo data-s='{s['id']}' data-d=redo onclick=\"pick('{s['id']}','redo')\">Redo</button>"
            f"<button class=replace data-s='{s['id']}' data-d=replace onclick=\"pick('{s['id']}','replace')\">I'll replace it</button></div>"
            f"<textarea id='n_{s['id']}' rows=2 placeholder='Note for a redo, e.g. darker, no people, show a lantern' "
            f"oninput=\"note('{s['id']}',this.value)\"></textarea></div></div>")
    shorts = sorted((folder / "out").glob("short_*.mp4")) if (folder / "out").exists() else []
    if shorts:
        out.append("<h2>Shorts</h2>")
        for sh in shorts:
            out.append(f"<div class=meta>{esc(sh.name)}</div><video controls preload=metadata "
                       f"style='max-width:360px' src='out/{esc(sh.name)}'></video>")
    thumb = "out/thumbnail.jpg" if (folder / "out" / "thumbnail.jpg").exists() else ""
    out.append("<h2>Upload details</h2>")
    if thumb:
        out.append(f"<img src='{thumb}' style='width:100%;max-width:640px;border-radius:12px'>")
    out.append(
        f"<label>Title<input id=p_title value='{esc(meta['title'])}' oninput=\"setp('title',this.value)\"></label>"
        f"<label>Thumbnail text<input id=p_thumbnail value='{esc(meta.get('thumbnail_text'))}' oninput=\"setp('thumbnail',this.value)\"></label>"
        f"<label>Description<textarea id=p_description rows=10 oninput=\"setp('description',this.value)\">{esc(meta.get('description'))}</textarea></label>"
        f"<label>Publish at (Pakistan time)<input id=p_when type=datetime-local oninput=\"setp('when',this.value)\"></label>"
        f"<label>Where<select id=p_platforms onchange=\"setp('platforms',this.value)\">"
        f"<option value=youtube>YouTube only</option><option value=all>YouTube + Shorts to Instagram, Facebook, TikTok</option></select></label>"
        f"<p class=meta>The upload will tick YouTube's \"altered or synthetic content\" box and set "
        f"the language to English.</p>")
    out.append("</main><div class=bar><span id=count></span>"
               "<button class=primary onclick='out()'>Save decisions</button></div>")
    data_js = {"folder": folder.name, "scenes": [{"id": s["id"]} for s in scenes]}
    out.append(f"<script>const DATA={json.dumps(data_js)};{JS}</script></body></html>")
    (folder / "review.html").write_text("\n".join(out))
    return folder / "review.html"


def apply(folder):
    from images import make_images
    folder = Path(folder)
    rv = json.loads((folder / "review.json").read_text())
    data = json.loads((folder / "scenes.json").read_text())
    redo, replace, ok = [], [], []
    for s in data["scenes"]:
        d = rv.get("scenes", {}).get(s["id"], {})
        if d.get("decision") == "redo":
            note = d.get("note", "").strip()
            if note:
                s["prompt"] = f"{s['prompt']} Change: {note}."
            g = folder / "images" / "_generated" / f"{s['id']}.png"
            if g.exists():
                g.unlink()
            redo.append(s["id"])
        elif d.get("decision") == "replace":
            replace.append(s["id"])
        elif d.get("decision") == "approve":
            ok.append(s["id"])
    p = rv.get("publish", {})
    for k_from, k_to in (("title", "title"), ("description", "description"),
                         ("thumbnail", "thumbnail_text")):
        if p.get(k_from):
            data["meta"][k_to] = p[k_from]
    if redo:
        make_images([s for s in data["scenes"] if s["id"] in redo], data["meta"]["series"],
                    folder / "images", generate=True)
    (folder / "scenes.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    all_ok = len(ok) == len(data["scenes"])
    state = {"approved_scenes": ok, "redo": redo, "replace": replace,
             "publish": p, "ready_to_publish": all_ok and bool(p.get("when"))}
    (folder / "approval.json").write_text(json.dumps(state, indent=1, ensure_ascii=False))
    print(f"approved {len(ok)}/{len(data['scenes'])}; redone {len(redo)}; waiting for your "
          f"images: {', '.join(replace) or 'none'}")
    if redo or replace:
        print("next: run `make_video.py render` again, then `review.py page` and review again")
    elif state["ready_to_publish"]:
        print("everything approved and a publish time is set: ready for the publishing step")


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_PUT(self):
        if self.path.strip("/") != "review.json":
            self.send_error(403)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        json.loads(body)
        Path("review.json").write_bytes(body)
        self.send_response(200)
        self.end_headers()


def serve(folder, port=8765):
    page(folder)
    os.chdir(folder)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except OSError:
        ip = "localhost"
    print(f"open on this laptop:  http://localhost:{port}/review.html")
    print(f"open on your phone (same Wi-Fi):  http://{ip}:{port}/review.html")
    http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("page", "serve", "apply"):
        sys.exit(__doc__)
    {"page": lambda f: print(page(f)), "serve": serve, "apply": apply}[sys.argv[1]](sys.argv[2])
