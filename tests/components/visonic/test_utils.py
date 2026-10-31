"""Test Visonic value conversion and identity helpers."""

from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant.components.visonic.const import VISONIC_ALARM
from homeassistant.components.visonic.utils import (
    capitalize,
    combine_partition_statuses,
    get_alarm_panel_unique_ident,
    get_utc_time,
    to_bool,
)
from homeassistant.components.visonic.visonic_types import AlarmPanelStatus
from homeassistant.util import dt as dt_util


@pytest.mark.parametrize(
    "order",
    [pytest.param((0, 1), id="forward"), pytest.param((1, 0), id="reverse")],
)
@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        pytest.param(
            (AlarmPanelStatus.ENTRY_DELAY, AlarmPanelStatus.ARMED_AWAY),
            AlarmPanelStatus.ENTRY_DELAY,
            id="entry-delay-over-away",
        ),
        pytest.param(
            (AlarmPanelStatus.ENTRY_DELAY, AlarmPanelStatus.ARMED_AWAY_INSTANT),
            AlarmPanelStatus.ENTRY_DELAY,
            id="entry-delay-over-instant-away",
        ),
        pytest.param(
            (AlarmPanelStatus.ENTRY_DELAY_INSTANT, AlarmPanelStatus.ARMING_AWAY),
            AlarmPanelStatus.ENTRY_DELAY_INSTANT,
            id="instant-entry-delay-over-arming",
        ),
        pytest.param(
            (AlarmPanelStatus.ENTRY_DELAY, AlarmPanelStatus.ENTRY_DELAY_INSTANT),
            AlarmPanelStatus.ENTRY_DELAY_INSTANT,
            id="both-entry-delays",
        ),
        pytest.param(
            (AlarmPanelStatus.ENTRY_DELAY, AlarmPanelStatus.TRIGGERED),
            AlarmPanelStatus.TRIGGERED,
            id="triggered-over-entry-delay",
        ),
        pytest.param(
            (AlarmPanelStatus.DISARMED, AlarmPanelStatus.ARMED_HOME),
            AlarmPanelStatus.ARMED_HOME,
            id="home-over-disarmed",
        ),
        pytest.param(
            (AlarmPanelStatus.ARMED_AWAY, AlarmPanelStatus.ARMED_HOME_BYPASS),
            AlarmPanelStatus.ARMED_HOME_BYPASS,
            id="preserve-armed-variants",
        ),
        pytest.param(
            (AlarmPanelStatus.ENTRY_DELAY, AlarmPanelStatus.DOWNLOADING),
            AlarmPanelStatus.DOWNLOADING,
            id="preserve-downloading",
        ),
        pytest.param(
            (AlarmPanelStatus.INSTALLER, AlarmPanelStatus.TRIGGERED),
            AlarmPanelStatus.TRIGGERED,
            id="triggered-over-maintenance",
        ),
    ],
)
def test_combine_partition_statuses(
    statuses: tuple[AlarmPanelStatus, AlarmPanelStatus],
    expected: AlarmPanelStatus,
    order: tuple[int, int],
) -> None:
    """Combine partition states consistently regardless of iteration order."""
    assert combine_partition_statuses(statuses[index] for index in order) is expected


def test_combine_no_partition_statuses() -> None:
    """A panel without active partitions has an unknown state."""
    assert combine_partition_statuses([]) is AlarmPanelStatus.UNKNOWN


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
