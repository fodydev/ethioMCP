# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Connector framework: automatic discovery, entry-point plugins, `ethiomcp setup|list|doctor|serve`.
- Isolated connectors: a per-connector venv with its own Python version, and a JSON-lines subprocess worker.
- `hornmorpho` connector: analyze, analyze_sentence (CoNLL-U), generate, phonetic.
- `geezorg` connector: dictionary lookup, verb paradigms, place names, WIC corpus search, archive browsing.
- `afrim` connector (afrim-data): keyboard transliteration to and from Ge'ez script, Amharic wordlist and names lookup, Ge'ez numerals, Ethiopian calendar conversion.
- Connector templates and `docs/adding-a-connector.md`.
