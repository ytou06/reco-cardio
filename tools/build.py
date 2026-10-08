#!/usr/bin/env python3
"""Construit le contenu de l'appli « Recos Cardio » à partir des sources rédigées.

Sources (jamais publiées en clair) :
  src/catalogue.json           disciplines et liste de toutes les recommandations
  src/guidelines/*.md          une recommandation par fichier (format décrit ci-dessous)
  src/questions/*.md           questions d'entraînement
  src/outils/*.md              posologies et guide pratique (même format que les chapitres)

Sortie : build/contenu.json (en clair, ignoré par git) puis chiffrement par tools/crypt.py.

Format des chapitres
--------------------
En-tête YAML simplifié entre deux lignes « --- » (clé: valeur).
  === id | Titre du chapitre        nouveau chapitre
  ## Titre / ### Sous-titre          titres
  > I A | texte                      recommandation (classe I, IIa, IIb, III ; niveau A, B, B1, B2, C)
  :::cles Titre … :::               points clés      :::nouveau Titre … :::  nouveautés
  :::attention Titre … :::          mise en garde    :::pratique Titre … :::  en pratique
  :::algo Titre                      étapes « Étiquette | texte » … :::
  :::details Titre … :::            bloc repliable
  | a | b |  (tableau markdown, ligne de séparation obligatoire)
  - puce / 1. liste numérotée
  @calc id                           calculateur intégré
  @outil id | texte                  lien vers une fiche de l'onglet Outils
  @lien texte | url                  lien externe
Mise en forme : **gras**, *italique*, `valeur` (chiffre mis en évidence), [texte](url).

Format des questions
--------------------
  ?? qi|kfp|dp | identifiant | reco=id | ch=chapitre | titre=…
  lignes de vignette clinique
  -- (dossier progressif : nouvelle étape, avec éventuellement un complément d'énoncé)
  ? qrm|qru|menu N | texte de la question
  [x] proposition juste :: justification
  [ ] proposition fausse :: justification
  [!] proposition dangereuse (question à réponses clés : annule la question) :: justification
  = explication (une ou plusieurs lignes)
"""
import glob, html, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSES = {"I", "IIa", "IIb", "III"}
LEVELS = {"A", "B", "B1", "B2", "C"}
ERR = []


def esc(s):
    return html.escape(s, quote=False)


def inline(s):
    s = esc(s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    s = re.sub(r"`([^`]+)`", r'<span class="num">\1</span>', s)
    s = s.replace(" ;", "&nbsp;;").replace(" :", "&nbsp;:").replace(" ?", "&nbsp;?").replace(" !", "&nbsp;!")
    return s


def parse_front(text, where):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        ERR.append(f"{where}: en-tête manquant")
        return {}, text
    meta = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def render_blocks(lines, where):
    """Transforme une suite de lignes en HTML."""
    out = []
    i = 0
    para = []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        raw = lines[i]
        l = raw.rstrip()
        s = l.strip()
        if not s:
            flush(); i += 1; continue
        if s.startswith(":::") and s != ":::":
            flush()
            kind, _, title = s[3:].partition(" ")
            j = i + 1
            depth = 1
            while j < len(lines):
                t = lines[j].strip()
                if t.startswith(":::") and t != ":::":
                    depth += 1
                elif t == ":::":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j >= len(lines):
                ERR.append(f"{where}: bloc :::{kind} non fermé")
            inner = lines[i + 1:j]
            out.append(render_box(kind, title.strip(), inner, where))
            i = j + 1
            continue
        if s.startswith("### "):
            flush(); out.append("<h4>" + inline(s[4:]) + "</h4>"); i += 1; continue
        if s.startswith("## "):
            flush(); out.append("<h3>" + inline(s[3:]) + "</h3>"); i += 1; continue
        if s.startswith("> "):
            flush()
            recos = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                recos.append(reco(lines[i].strip()[2:], where))
                i += 1
            out.append('<div class="recos">' + "".join(recos) + "</div>")
            continue
        if s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            out.append(table(rows, where))
            continue
        if re.match(r"^- ", s):
            flush()
            items = []
            while i < len(lines) and re.match(r"^\s*- ", lines[i]):
                items.append(lines[i].strip()[2:])
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() and not re.match(r"^\s*- ", lines[i]):
                    items[-1] += " " + lines[i].strip(); i += 1
            out.append("<ul>" + "".join("<li>" + inline(x) + "</li>" for x in items) + "</ul>")
            continue
        if re.match(r"^\d+\. ", s):
            flush()
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\. ", lines[i]):
                items.append(re.sub(r"^\s*\d+\. ", "", lines[i]).strip())
                i += 1
            out.append("<ol>" + "".join("<li>" + inline(x) + "</li>" for x in items) + "</ol>")
            continue
        if s.startswith("@calc "):
            flush(); out.append(f'<div class="calc" data-calc="{s[6:].strip()}"></div>'); i += 1; continue
        if s.startswith("@outil "):
            flush()
            oid, _, txt = s[7:].partition("|")
            out.append(f'<a class="xref" href="#outil-{oid.strip()}">{inline(txt.strip() or oid.strip())}</a>')
            i += 1; continue
        if s.startswith("@reco "):
            flush()
            target, _, txt = s[6:].partition("|")
            out.append(f'<a class="xref" href="#g-{target.strip()}">{inline(txt.strip())}</a>')
            i += 1; continue
        if s.startswith("@lien "):
            flush()
            txt, _, url = s[6:].partition("|")
            out.append(f'<a class="xref ext" href="{url.strip()}" target="_blank" rel="noopener">{inline(txt.strip())}</a>')
            i += 1; continue
        para.append(s)
        i += 1
    flush()
    return "\n".join(out)


def reco(s, where):
    m = re.match(r"^(I|IIa|IIb|III)\s+(A|B1|B2|B|C)\s*\|\s*(.+)$", s)
    if not m:
        ERR.append(f"{where}: recommandation mal formée : {s[:60]}")
        return ""
    c, lv, txt = m.groups()
    return f'<div class="reco c-{c}"><button class="cls" type="button" aria-label="Classe {c}, niveau {lv}">{c}<small>{lv}</small></button><p>{inline(txt)}</p></div>'


def table(rows, where):
    cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
    if len(cells) < 2 or not re.match(r"^[\s:\-|]+$", rows[1]):
        ERR.append(f"{where}: tableau sans ligne de séparation")
        return ""
    head, body = cells[0], cells[2:]
    h = "".join(f"<th>{inline(c)}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
    return f'<div class="tbl"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def render_algo(t, inner, where):
    """Algorithme : étapes « Étiquette | texte », liste numérotée « 1. … » (étiquette = début en gras
    ou partie avant « → »), sous-puces « - … » rattachées à l’étape précédente, tableaux markdown et
    paragraphes de note acceptés."""
    items = []          # ("st", label, text, [subs]) | ("raw", [lines])
    for l in inner:
        if not l.strip():
            continue
        st = l.strip()
        if st.startswith("|"):
            if items and items[-1][0] == "raw":
                items[-1][1].append(st)
            else:
                items.append(("raw", [st]))
            continue
        if st.startswith("- ") and items and items[-1][0] == "st" and l[:1] in (" ", "\t"):
            items[-1][3].append(st[2:])
            continue
        m = re.match(r"(\d+)\.\s+(.*)", st)
        if m:
            n, txt = m.groups()
            mb = re.match(r"\*\*(.+?)\*\*\s*[:→]\s*(.*)", txt)
            if mb and mb.group(2):
                lab, txt = mb.group(1), mb.group(2)
            elif " → " in txt and len(txt.split(" → ", 1)[0]) <= 70:
                lab, txt = txt.split(" → ", 1)
            else:
                lab = f"Étape {n}"
            items.append(("st", lab, txt, []))
            continue
        if st.startswith("- "):
            items.append(("st", "", st[2:], []))
            continue
        if "|" in st and not st.startswith("**"):
            k, _, v = st.partition("|")
            items.append(("st", k.strip(), v.strip(), []))
            continue
        items.append(("note", st))
    out = []
    for it in items:
        if it[0] == "st":
            sub = "".join(f"<li>{inline(x)}</li>" for x in it[3])
            sub = f"<ul>{sub}</ul>" if sub else ""
            lab = f"<b class=\"lab\">{inline(it[1])}</b>" if it[1] else ""
            out.append(f'<div class="st">{lab}{inline(it[2])}{sub}</div>')
        elif it[0] == "raw":
            out.append(f'<div class="st tb">{render_blocks(it[1], where)}</div>')
        else:
            out.append(f'<p class="an">{inline(it[1])}</p>')
    return f'<div class="blk-algo">{t}<div class="flow">{"".join(out)}</div></div>'


def render_box(kind, title, inner, where):
    t = f"<h3>{inline(title)}</h3>" if title else ""
    if kind == "cles":
        return f'<div class="s30">{t}{render_blocks(inner, where)}</div>'
    if kind in ("nouveau", "attention", "pratique"):
        cls = {"nouveau": "upd", "attention": "warn", "pratique": "prat"}[kind]
        return f'<div class="box {cls}">{t}{render_blocks(inner, where)}</div>'
    if kind == "algo":
        return render_algo(t, inner, where)
    if kind == "details":
        return f"<details><summary>{inline(title)}</summary><div>{render_blocks(inner, where)}</div></details>"
    ERR.append(f"{where}: type de bloc inconnu {kind}")
    return render_blocks(inner, where)


def parse_doc(path):
    text = open(path, encoding="utf-8").read()
    meta, body = parse_front(text, path)
    chapters = []
    cur = None
    for line in body.split("\n"):
        m = re.match(r"^===\s*([\w\-]+)\s*\|\s*(.+)$", line)
        if m:
            cur = {"id": m.group(1), "t": m.group(2).strip(), "lines": []}
            chapters.append(cur)
            continue
        if cur is None:
            if line.strip():
                ERR.append(f"{path}: texte avant le premier chapitre")
            continue
        cur["lines"].append(line)
    out = []
    ids = set()
    for c in chapters:
        if c["id"] in ids:
            ERR.append(f"{path}: chapitre en double {c['id']}")
        ids.add(c["id"])
        h = render_blocks(c["lines"], f"{os.path.basename(path)}#{c['id']}")
        nrec = h.count('class="reco ')
        out.append({"id": c["id"], "t": c["t"], "h": h, "n": nrec})
    return meta, out


def parse_options(lines, where):
    opts = []
    expl = []
    for l in lines:
        s = l.strip()
        m = re.match(r"^\[(x| |!)\]\s*(.+?)(?:\s*::\s*(.+))?$", s)
        if m:
            opts.append({"t": inline(m.group(2)), "ok": m.group(1) == "x", "kill": m.group(1) == "!",
                         "w": inline(m.group(3)) if m.group(3) else ""})
        elif s.startswith("= "):
            expl.append(s[2:])
        elif s == "=":
            continue
        elif s:
            if expl:
                expl.append(s)
            else:
                ERR.append(f"{where}: ligne inattendue dans les propositions : {s[:50]}")
    return opts, " ".join(expl)


def parse_questions(path, valid):
    text = open(path, encoding="utf-8").read()
    items = []
    blocks = re.split(r"^\?\?\s+", text, flags=re.M)
    for b in blocks[1:]:
        lines = b.split("\n")
        head = [x.strip() for x in lines[0].split("|")]
        kind = head[0]
        qid = head[1] if len(head) > 1 else ""
        attrs = {}
        for h in head[2:]:
            if "=" in h:
                k, v = h.split("=", 1)
                attrs[k.strip()] = v.strip()
        where = f"{os.path.basename(path)}:{qid}"
        if kind not in ("qi", "kfp", "dp"):
            ERR.append(f"{where}: type inconnu {kind}")
            continue
        g = attrs.get("reco")
        if g not in valid:
            ERR.append(f"{where}: reco inconnue {g}")
        elif attrs.get("ch") and attrs["ch"] not in valid[g]:
            ERR.append(f"{where}: chapitre inconnu {attrs.get('ch')}")
        body = lines[1:]
        # étapes séparées par « -- »
        steps_raw = [[]]
        for l in body:
            if l.strip() == "--":
                steps_raw.append([])
            else:
                steps_raw[-1].append(l)
        vignette = []
        steps = []
        for si, sr in enumerate(steps_raw):
            intro = []
            qs = []
            curq = None
            for l in sr:
                s = l.strip()
                m = re.match(r"^\?\s+(qrm|qru|menu)\s*(\d*)\s*\|\s*(.+)$", s)
                if m:
                    curq = {"f": m.group(1), "n": int(m.group(2) or 0), "q": inline(m.group(3)), "lines": []}
                    qs.append(curq)
                elif curq is not None:
                    curq["lines"].append(l)
                else:
                    intro.append(s)
            questions = []
            for q in qs:
                opts, expl = parse_options(q["lines"], where)
                nok = sum(o["ok"] for o in opts)
                if not opts or nok == 0:
                    ERR.append(f"{where}: question sans bonne réponse")
                if q["f"] == "qru" and nok != 1:
                    ERR.append(f"{where}: question à réponse unique avec {nok} bonnes réponses")
                if q["f"] == "menu" and (q["n"] < nok):
                    ERR.append(f"{where}: menu limité à {q['n']} réponses mais {nok} attendues")
                if not expl:
                    ERR.append(f"{where}: explication manquante")
                questions.append({"f": q["f"], "n": q["n"], "q": q["q"], "o": opts, "e": inline(expl)})
            txt = render_blocks(intro, where) if any(x for x in intro) else ""
            if si == 0 and kind != "dp":
                vignette = txt
                steps.append({"i": "", "qs": questions})
            elif si == 0:
                vignette = txt
                if questions:
                    steps.append({"i": "", "qs": questions})
            else:
                steps.append({"i": txt, "qs": questions})
        steps = [s for s in steps if s["qs"]]
        if not steps:
            ERR.append(f"{where}: aucune question")
            continue
        items.append({"id": qid, "k": kind, "g": g, "ch": attrs.get("ch", ""), "t": attrs.get("titre", ""),
                      "v": vignette, "s": steps})
    return items


def main():
    cat = json.load(open(os.path.join(ROOT, "src", "catalogue.json"), encoding="utf-8"))
    guides = []
    valid = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "src", "guidelines", "*.md"))):
        meta, chs = parse_doc(path)
        gid = meta.get("id")
        valid[gid] = {c["id"] for c in chs}
        guides.append({"id": gid, "t": meta.get("titre"), "tl": meta.get("titre_long"), "y": meta.get("annee"),
                       "d": meta.get("discipline"), "src": meta.get("source"), "v": meta.get("verification"),
                       "r": meta.get("resume"), "ch": chs})
    outils = []
    for path in sorted(glob.glob(os.path.join(ROOT, "src", "outils", "*.md"))):
        meta, chs = parse_doc(path)
        outils.append({"id": meta.get("id"), "t": meta.get("titre"), "r": meta.get("resume"), "sec": meta.get("section"),
                       "src": meta.get("sources"), "ch": chs})
    qs = []
    for path in sorted(glob.glob(os.path.join(ROOT, "src", "questions", "*.md"))):
        qs.extend(parse_questions(path, valid))
    seen = set()
    for q in qs:
        if q["id"] in seen:
            ERR.append(f"question en double : {q['id']}")
        seen.add(q["id"])
    # liens internes vers des recommandations du catalogue pas encore rédigées : affichés « à venir »
    allg = {g["id"]: g for g in guides}
    catids = {x.get("id") for x in cat["liste"] if x.get("id")}
    def soon(m):
        gid = m.group(1).split("--")[0]
        if gid in allg or gid not in catids:
            return m.group(0)
        return f'<span class="xref soon">{m.group(2)} · à venir</span>'
    for d in guides + outils:
        for c in d["ch"]:
            c["h"] = re.sub(r'<a class="xref" href="#g-([\w\-]+)">(.*?)</a>', soon, c["h"])
    tools = {o["id"] for o in outils}
    blob = json.dumps([g["ch"] for g in guides] + [o["ch"] for o in outils], ensure_ascii=False)
    for t in re.findall(r'href=\\"#outil-([\w\-]+)\\"', blob):
        if t not in tools:
            ERR.append(f"lien vers un outil inconnu : {t}")
    for href in re.findall(r'href=\\"#g-([\w\-]+)\\"', blob):
        t = (href.split("--", 1) + [""])[:2]
        if t[0] not in allg or (t[1] and t[1] not in valid.get(t[0], set())):
            ERR.append(f"lien vers un chapitre inconnu : {t}")
    data = {"cat": cat, "g": guides, "o": outils, "q": qs, "built": os.environ.get("BUILD_DATE", "")}
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    with open(os.path.join(ROOT, "build", "contenu.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    n_rec = sum(c["n"] for g in guides for c in g["ch"])
    kinds = {k: sum(1 for q in qs if q["k"] == k) for k in ("qi", "kfp", "dp")}
    print(f"{len(guides)} recommandations, {sum(len(g['ch']) for g in guides)} chapitres, {n_rec} recommandations classées, "
          f"{len(outils)} fiches outils, questions {kinds}", file=sys.stderr)
    if ERR:
        print("\n".join("ERREUR " + e for e in ERR), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
