"""Test Visonic value conversion and identity helpers."""

from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant.components.visonic.const import VISONIC_ALARM
from homeassistant.components.visonic.utils import (
    capitalize,
    get_alarm_panel_unique_ident,
    get_utc_time,
    to_bool,
)
from homeassistant.util import dt as dt_util


def test_to_bool() -> None:
    """Test to_bool."""
    assert to_bool(True) is True
    assert to_bool(False) is False
    assert to_bool(1) is True
    assert to_bool(0) is False
    assert to_bool(-1) is True
    assert to_bool("true") is True
    assert to_bool("false") is False
    assert to_bool("0") is False
    assert to_bool("1") is True
    assert to_bool("no") is False
    assert to_bool("YES") is True
    assert to_bool(None) is False


@pytest.mark.parametrize(
    ("panel_identifier", "expected"),
    [
        pytest.param(0, VISONIC_ALARM, id="panel-zero"),
        pytest.param(2, f"{VISONIC_ALARM} P2", id="numbered-panel"),
        pytest.param("entry-id", f"{VISONIC_ALARM} entry-id", id="entry-identifier"),
    ],
)
def test_panel_identifier(panel_identifier: int | str, expected: str) -> None:
    """Preserve numbered and entry-based panel identities."""
    assert get_alarm_panel_unique_ident(panel_identifier) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("", "", id="empty"),
        pytest.param("VISONIC Panel", "Visonic panel", id="mixed-case"),
    ],
)
def test_capitalize(value: str, expected: str) -> None:
    """Handle empty and mixed-case display text."""
    assert capitalize(value) == expected


def test_get_utc_time() -> None:
    """Use Home Assistant's UTC clock."""
    now: datetime = dt_util.utcnow()
    with patch(
        "homeassistant.components.visonic.utils.dt_util.utcnow", return_value=now
    ):
        assert get_utc_time() == now
