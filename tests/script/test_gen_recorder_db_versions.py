"""Tests for the gen_recorder_db_versions script."""

from datetime import date
import sys
from unittest.mock import patch
import urllib.error

import pytest

from script import gen_recorder_db_versions as gen

# endoflife.date exposes `lts` as a boolean for most cycles, but as the date the
# cycle became LTS for some (e.g. MySQL 8.0), and `eol` as a date string or, when
# no end of life is announced yet, the boolean false.
MARIADB_CYCLES = [
    {"cycle": "12.3", "lts": True, "eol": "2029-06-12"},  # supported LTS
    {"cycle": "12.2", "lts": False, "eol": "2026-05-28"},  # newest non-LTS
    {"cycle": "11.8", "lts": True, "eol": "2028-06-04"},  # supported LTS
    {"cycle": "10.6", "lts": True, "eol": "2026-07-06"},  # LTS past end of life
    {"cycle": "10.3", "lts": False, "eol": "2023-05-25"},  # old non-LTS
]
MYSQL_CYCLES = [
    {"cycle": "9.7", "lts": True, "eol": "2034-04-21"},  # supported LTS (bool)
    {"cycle": "9.6", "lts": False, "eol": "2026-04-21"},  # newest non-LTS
    {"cycle": "8.4", "lts": True, "eol": "2032-04-30"},  # supported LTS (bool)
    {"cycle": "8.0", "lts": "2023-07-18", "eol": "2026-04-30"},  # LTS-as-date, past EOL
]


@pytest.mark.parametrize(
    ("cycles", "expected"),
    [
        (MARIADB_CYCLES, {"supported_lts": ["11.8", "12.3"], "latest_non_lts": "12.2"}),
        (MYSQL_CYCLES, {"supported_lts": ["8.4", "9.7"], "latest_non_lts": "9.6"}),
    ],
    ids=["mariadb", "mysql"],
)
def test_engine_versions(cycles: list[dict], expected: dict) -> None:
    """Test end-of-life filtering, LTS bool/date handling, and series ordering."""
    assert gen._engine_versions(cycles, date(2026, 8, 20)) == expected


def test_eol_handles_missing_and_date() -> None:
    """Test a missing end-of-life date maps to date.max and a date string is parsed."""
    assert gen._eol({"eol": False}) == date.max
    assert gen._eol({"eol": "2028-02-16"}) == date(2028, 2, 16)


def test_render_matches_committed() -> None:
    """Test the committed file is exactly what render() produces."""
    assert gen.render(gen.load_committed()) == gen.OUTPUT_FILE.read_text()


def test_main_validate_up_to_date() -> None:
    """Test validate succeeds when the committed file matches the fetched data."""
    with (
        patch.object(gen, "fetch_versions", return_value=gen.load_committed()),
        patch.object(sys, "argv", ["prog", "validate"]),
    ):
        assert gen.main() == 0


def test_main_validate_out_of_date(capsys: pytest.CaptureFixture[str]) -> None:
    """Test validate fails and reports the generated file path when out of date."""
    stale = {
        "mariadb": {"supported_lts": ["0.0"], "latest_non_lts": "0.0"},
        "mysql": {"supported_lts": ["0.0"], "latest_non_lts": "0.0"},
    }
    with (
        patch.object(gen, "fetch_versions", return_value=stale),
        patch.object(sys, "argv", ["prog", "validate"]),
    ):
        assert gen.main() == 1
    output = capsys.readouterr().out
    assert "homeassistant/generated/recorder_database_versions.py" in output
    assert "components/recorder/database_versions.py" not in output


def test_main_validate_skips_on_network_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test validate skips (instead of failing) when endoflife.date is unreachable."""
    with (
        patch.object(gen, "fetch_versions", side_effect=urllib.error.URLError("boom")),
        patch.object(sys, "argv", ["prog", "validate"]),
    ):
        assert gen.main() == 0
    assert "Skipping validation" in capsys.readouterr().out
