"""Test the alexa_locales script."""

from pathlib import Path

import pytest
import requests_mock
from syrupy import SnapshotAssertion

from script.alexa_locales import SITE, run_script


def test_alexa_locales(
    capsys: pytest.CaptureFixture[str],
    requests_mock: requests_mock.Mocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Test alexa_locales script."""
    fixture_file = (
        Path(__file__).parent.parent / "fixtures/non_packaged_scripts/alexa_locales.txt"
    )
    requests_mock.get(
        SITE,
        text=fixture_file.read_text(encoding="utf-8"),
    )

    run_script()

    captured = capsys.readouterr()
    assert captured.out == snapshot
