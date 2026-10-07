#!/usr/bin/env python3
"""Chiffrement du contenu de l'appli Recos Cardio.

Le contenu publié (data/content.json) est chiffré : AES-256-GCM, clé dérivée du
mot de passe par PBKDF2-SHA256. Le mot de passe n'est jamais écrit dans le dépôt :
il est lu dans la variable d'environnement RC_PASSWORD.

  python3 tools/crypt.py encrypt < build/contenu.json   # (re)chiffre, garde le même sel
  python3 tools/crypt.py decrypt > contenu.json           # déchiffre vers la sortie standard
  python3 tools/crypt.py check                            # vérifie que le mot de passe ouvre le contenu
"""
import base64, json, os, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "content.json")
ITER = 600000

b64e = lambda b: base64.b64encode(b).decode()
b64d = lambda s: base64.b64decode(s)


def password():
    pw = os.environ.get("RC_PASSWORD")
    if not pw:
        sys.exit("RC_PASSWORD manquant")
    return pw.encode()


def key(kdf):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b64d(kdf["salt"]), iterations=kdf["iter"]).derive(password())


def load():
    with open(DATA) as f:
        return json.load(f)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "encrypt":
        raw = sys.stdin.buffer.read()
        json.loads(raw)  # contrôle : du JSON valide
        if os.path.exists(DATA):  # même mot de passe obligatoire pour garder les téléphones déverrouillés
            old = load()
            kdf = old["kdf"]
            AESGCM(key(kdf)).decrypt(b64d(old["iv"]), b64d(old["ct"]), None)
        else:
            kdf = {"alg": "PBKDF2-SHA256", "iter": ITER, "salt": b64e(os.urandom(16))}
        iv = os.urandom(12)
        blob = {"v": 1, "kdf": kdf, "iv": b64e(iv), "ct": b64e(AESGCM(key(kdf)).encrypt(iv, raw, None))}
        os.makedirs(os.path.dirname(DATA), exist_ok=True)
        with open(DATA, "w") as f:
            json.dump(blob, f)
        print("chiffré :", DATA, f"({len(raw)} octets en clair)", file=sys.stderr)
    elif cmd == "decrypt":
        d = load()
        sys.stdout.buffer.write(AESGCM(key(d["kdf"])).decrypt(b64d(d["iv"]), b64d(d["ct"]), None))
    elif cmd == "check":
        d = load()
        n = len(AESGCM(key(d["kdf"])).decrypt(b64d(d["iv"]), b64d(d["ct"]), None))
        print("ok :", n, "octets déchiffrés")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
