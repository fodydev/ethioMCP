"""HornMorpho connector: morphology for Amharic, Tigrinya, Oromo and Tigre.

Upstream: https://github.com/hltdi/HornMorpho (GPL-3.0). It runs in its own
venv and process, so the server never imports it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ethiomcp.core import ConnectorError, IsolatedConnector, SetupContext
from ethiomcp.core.envs import env_python, run_in_env

# ISO 639 code (the codes the LLM sees) -> HornMorpho's internal code.
LANGUAGES: dict[str, dict[str, str]] = {
    "am": {"hm": "a", "name": "Amharic"},
    "ti": {"hm": "t", "name": "Tigrinya"},
    "om": {"hm": "o", "name": "Oromo"},
    "tig": {"hm": "te", "name": "Tigre"},
}
DEFAULT_SETUP_LANGS = "am,ti,om"


def hm_code(lang: str) -> str:
    lang = lang.strip().lower()
    if lang in LANGUAGES:
        return LANGUAGES[lang]["hm"]
    if lang in {v["hm"] for v in LANGUAGES.values()}:
        return lang
    raise ConnectorError(f"unsupported language {lang!r}; use one of {', '.join(LANGUAGES)}")


class HornMorphoConnector(IsolatedConnector):
    name = "hornmorpho"
    title = "HornMorpho morphological analyzer/generator"
    description = (
        "Morphological analysis, segmentation, generation and phonetic (gemination-aware) "
        "transcription for Amharic, Tigrinya, Oromo and Tigre, with UD and UniMorph features."
    )
    source_url = "https://github.com/hltdi/HornMorpho"
    license = "GPL-3.0 (runs as a separate process)"

    python = ">=3.9,<3.13"
    # The upstream git repo is ~2.3 GB, so install the published wheel (stored with Git LFS).
    version = "5.3.6"
    requirements = [
        "hornmorpho @ https://media.githubusercontent.com/media/hltdi/HornMorpho/master/dist/"
        f"hornmorpho-{version}-py3-none-any.whl"
    ]
    worker_script = Path(__file__).with_name("worker_main.py")
    call_timeout = 600.0  # loading a language for the first time can be slow

    def post_install(self, ctx: SetupContext) -> None:
        langs = ctx.options.get("langs", DEFAULT_SETUP_LANGS)
        for lang in (x for x in langs.split(",") if x.strip()):
            code = hm_code(lang)
            ctx.log(f"Downloading HornMorpho data for {lang} ({code})")
            run_in_env(
                self.venv_dir,
                f"import hm; hm.download({code!r})",
                log=ctx.log,
            )

    def is_ready(self) -> bool:
        return env_python(self.venv_dir).exists()

    def _wrap(self, lang: str, payload: Any) -> dict[str, Any]:
        return {"language": lang, "result": payload, **self.attribution}

    def register(self, mcp: MCPServer) -> None:
        @self.tool(mcp, needs_setup=False)
        def languages() -> dict[str, Any]:
            """List the languages HornMorpho supports, with their codes for the other
            hornmorpho tools."""
            langs = [{"code": k, "name": v["name"]} for k, v in LANGUAGES.items()]
            return {"languages": langs, **self.attribution}

        @self.tool(mcp)
        def analyze(
            word: str, lang: str = "am", guess: bool = False, include_feats: bool = False
        ) -> dict[str, Any]:
            """Analyze one word in Ge'ez script (e.g. 'የቤታችን').

            Returns every analysis, with its lemma, root, part of speech,
            segmentation ('seg', stem between < >), Universal Dependencies
            features ('udfeats'), UniMorph tags ('um'), a transliteration
            ('translit', gemination shown) and per-morpheme details.
            guess=True guesses analyses for unknown words. include_feats=True
            also returns HornMorpho's full feature structure, which shows the
            feature names that hornmorpho_generate accepts.
            lang: am | ti | om | tig.
            """
            result = self.call(
                "analyze", lang=hm_code(lang), word=word, guess=guess, include_feats=include_feats
            )
            return self._wrap(lang, result)

        @self.tool(mcp)
        def analyze_sentence(sentence: str, lang: str = "am") -> dict[str, Any]:
            """Analyze a tokenized sentence (words separated by spaces, punctuation
            split off). Returns a CoNLL-U annotation with lemmas, UPOS, features
            and morpheme segmentation (clitics become separate tokens). Full
            dependency trees are not predicted. lang: am | ti."""
            return self._wrap(
                lang, self.call("analyze_sentence", lang=hm_code(lang), sentence=sentence)
            )

        @self.tool(mcp)
        def generate(
            root: str, features: str = "", lang: str = "am", pos: str | None = None
        ) -> dict[str, Any]:
            """Generate word forms from a root or lemma in Ge'ez script.

            root: a consonantal root such as 'ስብር', or a lemma such as 'ሰበረ'
            (its root is found automatically).
            features: a HornMorpho feature structure, for example '[sb=[+p1,+plr]]'
            for a 1st person plural subject. Run hornmorpho_analyze with
            include_feats=True on a similar word to see the feature names.
            pos: 'v' (verb), 'n' (noun), 'vn' (verbal noun), 'cop'. Without pos
            and features, the citation forms of each derived POS are returned.
            """
            return self._wrap(
                lang,
                self.call("generate", lang=hm_code(lang), root=root, features=features, pos=pos),
            )

        @self.tool(mcp)
        def phonetic(word: str, lang: str = "am") -> dict[str, Any]:
            """Phonetic transliteration of a Ge'ez script word, showing gemination
            and the epenthetic vowels the script does not write. One entry per
            distinct reading (e.g. ሰበረ -> səbbərə or səbərə)."""
            return self._wrap(lang, self.call("phonetic", lang=hm_code(lang), word=word))
