"""Tests for Elke27 entity helpers."""

from datetime import UTC, datetime

from elke27_lib import PanelInfo, PanelSnapshot, TableInfo

from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.components.elke27.helpers import (
    build_unique_id,
    device_info_for_entry,
    get_panel_field,
    sanitize_name,
    unique_base,
)
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class _Hub:
    def __init__(self) -> None:
        self.panel_name = "Panel A"


def _snapshot(panel: PanelInfo | None = None) -> PanelSnapshot:
    return PanelSnapshot(
        panel=panel or PanelInfo(),
        table_info=TableInfo(),
        areas={},
        zones={},
        zone_definitions={},
        outputs={},
        output_definitions={},
        lights={},
        barriers={},
        locks={},
        thermostats={},
        version=1,
        updated_at=datetime.now(UTC),
    )


async def test_get_panel_field_handles_typed_snapshot() -> None:
    """Verify panel fields are extracted from typed snapshots."""
    snapshot = _snapshot(
        PanelInfo(
            mac="aa:bb:cc:dd:ee:ff",
            serial="1234",
            model="E27",
            firmware="1.0",
        )
    )

    assert get_panel_field(snapshot, "Panel A", "name") == "Panel A"
    assert get_panel_field(snapshot, None, "mac") == "aa:bb:cc:dd:ee:ff"
    assert get_panel_field(snapshot, None, "serial") == "1234"
    assert get_panel_field(snapshot, None, "model") == "E27"
    assert get_panel_field(snapshot, None, "firmware") == "1.0"
    assert get_panel_field(snapshot, None, "unknown") is None


async def test_device_info_and_unique_base(hass: HomeAssistant) -> None:
    """Verify device info and unique base use the config entry client ID."""
    entry = MockConfigEntry(
        domain="elke27",
        data={CONF_HOST: "192.168.1.10", CONF_CLIENT_ID: "entryclientid"},
    )
    entry.add_to_hass(hass)
    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    coordinator.async_set_updated_data(
        _snapshot(
            PanelInfo(
                mac="aa:bb:cc:dd:ee:ff",
                serial="1234",
                model="E27",
                firmware="1.0",
            )
        )
    )
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    device_info = device_info_for_entry(hub, coordinator, entry)
    assert device_info["name"] == "Panel A"
    assert device_info["serial_number"] == "1234"
    assert device_info["identifiers"] == {("elke27", "entryclientid")}
    assert unique_base(entry) == "entryclientid"

    coordinator.async_set_updated_data(_snapshot())
    assert unique_base(entry) == "entryclientid"

    hass.config_entries.async_update_entry(entry, unique_id="entry-unique")
    hass.config_entries.async_update_entry(
        entry,
        data={CONF_HOST: entry.data[CONF_HOST]},
    )
    assert unique_base(entry) == "entry-unique"
    device_info = device_info_for_entry(hub, coordinator, entry)
    assert device_info["identifiers"] == {("elke27", "entry-unique")}

    hass.config_entries.async_update_entry(entry, unique_id=None)
    assert unique_base(entry) == entry.entry_id


def test_build_unique_id() -> None:
    """Verify unique ID formatting."""
    assert build_unique_id("entryclientid", 3) == "entryclientid:3"


def test_sanitize_and_panel_field() -> None:
    """Verify sanitize_name and get_panel_field behavior."""
    assert sanitize_name(None) is None
    assert get_panel_field(None, None, "name") is None
