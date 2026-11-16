import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """An empty ETHIOMCP_DATA_DIR."""
    monkeypatch.setenv("ETHIOMCP_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def geezorg(data_dir):
    """A GeezorgDataConnector whose repo is the fixture mini-archive."""
    from ethiomcp.connectors.geezorg_data import GeezorgDataConnector

    repo = data_dir / "geezorg" / "repo"
    shutil.copytree(FIXTURES / "geezorg_repo", repo)
    (repo / ".git").mkdir()  # git cannot commit a nested .git, so create the marker here
    return GeezorgDataConnector()


@pytest.fixture
def afrim(data_dir):
    """An AfrimDataConnector whose repo is the fixture mini afrim-data checkout."""
    from ethiomcp.connectors.afrim_data import AfrimDataConnector

    shutil.copytree(FIXTURES / "afrim_repo", data_dir / "afrim" / "repo")
    return AfrimDataConnector()
