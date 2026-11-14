"""HornMorpho worker. It runs inside the hornmorpho venv, not in the server.

STDLIB + hm ONLY, Python 3.8+ syntax. It talks to the server with the JSON-lines
protocol in ``ethiomcp/core/worker_protocol.py``.
"""

import contextlib
import importlib.util
import io
import os
import sys

_proto_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "core", "worker_protocol.py"
)
_spec = importlib.util.spec_from_file_location("worker_protocol", _proto_path)
proto = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(proto)

proto.protect_stdout()  # `import hm` prints a banner

_hm = None


def hm():
    global _hm
    if _hm is None:
        import hm as module

        _hm = module
    return _hm


def _jsonable(obj):
    """Convert HornMorpho's output to plain JSON types."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    return str(obj)


def _captured(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args, **kwargs)
    return result, buf.getvalue()


KEEP = ("lemma", "root", "pos", "seg", "udfeats", "um", "freq")


def _clean(a, include_feats=False):
    """Keep the fields useful to a linguist and drop the empty slots."""
    out = {k: a[k] for k in KEEP if a.get(k) not in (None, "")}
    for misc in a.get("misc") or []:
        if isinstance(misc, str) and misc.startswith("Translit="):
            out["translit"] = misc[len("Translit=") :]
    morphs = []
    for m in (a.get("pre") or []) + [a.get("stem")] + (a.get("suf") or []):
        if isinstance(m, dict):
            morphs.append({k: v for k, v in m.items() if v not in (None, "", 0, [])})
    if morphs:
        out["morphemes"] = morphs
    if include_feats and a.get("feats"):
        out["feats"] = a["feats"]
    return _jsonable(out)


def analyze(lang, word, guess=False, include_feats=False):
    result, _ = _captured(hm().anal, lang, word, guess=guess)
    return [_clean(a, include_feats) for a in (result or [])]


def analyze_sentence(lang, sentence):
    sent, _ = _captured(hm().anal_sentence, lang, sentence)
    if sent is None:
        return {"conllu": ""}
    _, text = _captured(sent.print_conllu)
    return {"conllu": text.strip()}


def _gen(lang, root, features, pos):
    kwargs = {}
    if features:
        kwargs["features"] = features
    if pos:
        kwargs["pos"] = pos
    result, log = _captured(hm().gen, lang, root, **kwargs)
    return result or [], log.strip()


def generate(lang, root, features="", pos=None):
    words, log = _gen(lang, root, features, pos)
    used_root = root
    if not words:
        # The caller may have given a lemma (e.g. ሰበረ): analyze it to find the root (ስብር).
        anals, _ = _captured(hm().anal, lang, root)
        roots = []
        for a in anals or []:
            r = str(a.get("root") or "").split(":")[0]
            if r and r != root and r not in roots:
                roots.append(r)
        for r in roots:
            words, log = _gen(lang, r, features, pos)
            if words:
                used_root = r
                break
    return {"root": used_root, "words": _jsonable(words), "messages": log}


def phonetic(lang, word):
    """Transliteration with gemination and epenthetic vowels, one item per distinct reading."""
    result, _ = _captured(hm().anal, lang, word)
    readings = []
    for a in result or []:
        c = _clean(a)
        t = c.get("translit")
        if t and t not in [r["translit"] for r in readings]:
            readings.append({"translit": t, "lemma": c.get("lemma"), "pos": c.get("pos")})
    return readings


def version():
    return getattr(hm(), "__version__", None) or getattr(hm(), "VERSION", None)


if __name__ == "__main__":
    proto.serve(
        {
            "analyze": analyze,
            "analyze_sentence": analyze_sentence,
            "generate": generate,
            "phonetic": phonetic,
            "version": version,
        },
        info={"connector": "hornmorpho", "cwd": os.getcwd(), "argv0": sys.argv[0]},
    )
