"""Tests for Easywave device storage helpers."""

from homeassistant.components.easywave.devices import get_stored_devices
from homeassistant.const import CONF_DEVICES

from tests.common import MockConfigEntry


def test_get_stored_devices_returns_empty_for_non_list_options() -> None:
    """Malformed options storage is treated as no configured devices."""
    entry = MockConfigEntry(domain="easywave", options={CONF_DEVICES: "invalid"})
    assert get_stored_devices(entry) == []
