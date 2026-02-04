"""Tests for Elke27 entity helpers."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.components.elke27.entity import (
    build_unique_id,
    device_info_for_entry,
    get_panel_field,
    sanitize_name,
    unique_base,
)
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class _Hub:
    def __init__(self) -> None:
        self.panel_name = "Panel A"


async def test_get_panel_field_handles_dict_and_object() -> None:
    """Verify panel fields are extracted from dict and object snapshots."""
    snapshot = SimpleNamespace(
        panel_info=SimpleNamespace(
            name="Panel A",
            mac="aa:bb:cc:dd:ee:ff",
            serial="1234",
        )
    )
    assert get_panel_field(snapshot, None, "name") == "Panel A"
    assert get_panel_field(snapshot, None, "mac") == "aa:bb:cc:dd:ee:ff"
    assert get_panel_field(snapshot, None, "serial") == "1234"

    snapshot_dict = SimpleNamespace(
        panel_info={"panel_name": "Panel B", "panel_mac": "00:11", "panel_serial": "1"}
    )
    assert get_panel_field(snapshot_dict, None, "name") == "Panel B"
    assert get_panel_field(snapshot_dict, None, "mac") == "00:11"
    assert get_panel_field(snapshot_dict, None, "serial") == "1"


async def test_device_info_and_unique_base(hass: HomeAssistant) -> None:
    """Verify device info and unique base prefer MAC and integration serial."""
    entry = MockConfigEntry(
        domain="elke27",
        data={CONF_HOST: "192.168.1.10", "integration_serial": "112233"},
    )
    entry.add_to_hass(hass)
    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        panel_info=SimpleNamespace(
            name="Panel A",
            mac="aa:bb:cc:dd:ee:ff",
            serial="1234",
            model="E27",
            firmware="1.0",
        )
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    device_info = device_info_for_entry(hub, coordinator, entry)
    assert device_info["name"] == "Panel A"
    assert device_info["serial_number"] == "1234"
    assert unique_base(hub, coordinator, entry) == "aa:bb:cc:dd:ee:ff"

    coordinator.async_set_updated_data(SimpleNamespace(panel_info=None))
    assert unique_base(hub, coordinator, entry) == "112233"

    entry.unique_id = "entry-unique"
    entry.data.pop("integration_serial", None)
    assert unique_base(hub, coordinator, entry) == "entry-unique"

    entry.unique_id = None
    assert unique_base(hub, coordinator, entry) == entry.data[CONF_HOST]


def test_build_unique_id() -> None:
    """Verify unique ID formatting."""
    assert build_unique_id("aa:bb", "zone", 3) == "aa:bb:zone:3"


def test_sanitize_and_panel_field() -> None:
    """Verify sanitize_name and get_panel_field behavior."""
    assert sanitize_name(None) is None
    assert get_panel_field(None, None, "name") is None
    snapshot = SimpleNamespace(panel_info={"model": "E27"})
    assert get_panel_field(snapshot, None, "model") == "E27"
