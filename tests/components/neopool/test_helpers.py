"""Tests for the NeoPool helper functions."""

from unittest.mock import patch

from homeassistant.components.neopool.helpers import (
    is_device_time_out_of_sync,
    prepare_device_time,
)
from homeassistant.core import HomeAssistant


def test_prepare_device_time_returns_unix_timestamp(hass: HomeAssistant) -> None:
    """prepare_device_time returns a positive 32-bit unix timestamp."""
    result = prepare_device_time(hass)
    assert isinstance(result, int)
    assert 0 < result < 0x100000000


# ``MBF_PAR_TIME`` and ``prepare_device_time`` share a TZ-less wall-clock epoch,
# so the tests compare the two directly and never decode through a timezone.
_NOW_WALL = 1_700_000_000


def test_is_device_time_out_of_sync_within_threshold(hass: HomeAssistant) -> None:
    """A small drift between device and HA returns False."""
    data = {"MBF_PAR_TIME": _NOW_WALL}
    with patch(
        "homeassistant.components.neopool.helpers.prepare_device_time",
        return_value=_NOW_WALL,
    ):
        assert is_device_time_out_of_sync(data, hass, threshold_seconds=60) is False


def test_is_device_time_out_of_sync_above_threshold(hass: HomeAssistant) -> None:
    """A drift larger than threshold returns True."""
    data = {"MBF_PAR_TIME": _NOW_WALL - 7200}  # device 2 hours behind
    with patch(
        "homeassistant.components.neopool.helpers.prepare_device_time",
        return_value=_NOW_WALL,
    ):
        assert is_device_time_out_of_sync(data, hass, threshold_seconds=60) is True


def test_is_device_time_out_of_sync_no_data(hass: HomeAssistant) -> None:
    """Missing time registers means we cannot detect drift, so return False."""
    assert is_device_time_out_of_sync({}, hass, threshold_seconds=60) is False


def test_is_device_time_out_of_sync_default_threshold(hass: HomeAssistant) -> None:
    """The default tolerance is loose: a drift under 5 minutes is ignored."""
    data = {"MBF_PAR_TIME": _NOW_WALL - 120}  # device 2 minutes behind
    with patch(
        "homeassistant.components.neopool.helpers.prepare_device_time",
        return_value=_NOW_WALL,
    ):
        assert is_device_time_out_of_sync(data, hass) is False
        assert is_device_time_out_of_sync(data, hass, threshold_seconds=60) is True
