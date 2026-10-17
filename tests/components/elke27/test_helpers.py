"""Tests for Elke27 entity helpers."""

from unittest.mock import patch

from elke27_lib import PanelInfo, PanelSnapshot, TableInfo

from homeassistant.components.elke27.const import CONF_LINK_KEYS_JSON, DEFAULT_PORT
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.components.elke27.helpers import (
    build_unique_id,
    device_info_for_entry,
    unique_base,
)
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


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
        updated_at=dt_util.utcnow(),
    )


def _entry_data() -> dict[str, str | int]:
    """Return minimal stored config data."""
    return {
        CONF_HOST: "192.168.1.10",
        CONF_PORT: DEFAULT_PORT,
        CONF_LINK_KEYS_JSON: "{}",
        CONF_CLIENT_ID: "entryclientid",
    }


async def test_device_info_and_unique_base(hass: HomeAssistant) -> None:
    """Verify device info and unique base use the config entry client ID."""
    entry = MockConfigEntry(
        domain="elke27",
        data=_entry_data(),
    )
    entry.add_to_hass(hass)
    coordinator = Elke27DataUpdateCoordinator(hass, entry)
    coordinator.async_set_updated_data(
        _snapshot(
            PanelInfo(
                mac="aa:bb:cc:dd:ee:ff",
                serial="1234",
                model="E27",
                firmware="1.0",
                panel_name="Snapshot Panel",
            )
        )
    )
    entry.runtime_data = Elke27RuntimeData(coordinator=coordinator)

    device_info = device_info_for_entry(coordinator, entry)
    assert device_info["name"] == "Snapshot Panel"
    assert device_info["serial_number"] == "1234"
    assert device_info["connections"] == {
        ("mac", "aa:bb:cc:dd:ee:ff"),
    }
    assert device_info["identifiers"] == {("elke27", "entryclientid")}
    assert device_info["manufacturer"] == "Elk Products"
    assert unique_base(entry) == "entryclientid"

    hass.config_entries.async_update_entry(entry, unique_id="entry-unique")
    assert unique_base(entry) == "entry-unique"

    hass.config_entries.async_update_entry(entry, unique_id=None)
    coordinator.async_set_updated_data(_snapshot())
    assert unique_base(entry) == "entryclientid"

    hass.config_entries.async_update_entry(entry, unique_id="entry-unique")
    hass.config_entries.async_update_entry(
        entry,
        data={CONF_HOST: entry.data[CONF_HOST]},
    )
    assert unique_base(entry) == "entry-unique"
    device_info = device_info_for_entry(coordinator, entry)
    assert device_info["identifiers"] == {("elke27", "entry-unique")}

    hass.config_entries.async_update_entry(entry, unique_id=None)
    assert unique_base(entry) == entry.entry_id


async def test_device_info_ignores_invalid_mac(hass: HomeAssistant) -> None:
    """Verify invalid panel MAC values do not break device info setup."""
    entry = MockConfigEntry(
        domain="elke27",
        data=_entry_data(),
    )
    entry.add_to_hass(hass)
    coordinator = Elke27DataUpdateCoordinator(hass, entry)
    coordinator.async_set_updated_data(_snapshot(PanelInfo(mac="aa:bb:cc:dd:ee:ff")))
    entry.runtime_data = Elke27RuntimeData(coordinator=coordinator)

    with patch(
        "homeassistant.components.elke27.helpers.format_mac",
        side_effect=ValueError,
    ):
        device_info = device_info_for_entry(coordinator, entry)

    assert device_info["connections"] == set()


async def test_device_info_uses_title_fallback(hass: HomeAssistant) -> None:
    """Verify entry title is used when the snapshot has no panel name."""
    entry = MockConfigEntry(
        domain="elke27",
        title="Panel\x00 One",
        data=_entry_data(),
    )
    entry.add_to_hass(hass)
    coordinator = Elke27DataUpdateCoordinator(hass, entry)
    coordinator.async_set_updated_data(_snapshot())
    entry.runtime_data = Elke27RuntimeData(coordinator=coordinator)

    device_info = device_info_for_entry(coordinator, entry)

    assert device_info["name"] == "Panel\x00 One"


def test_build_unique_id() -> None:
    """Verify unique ID formatting."""
    assert build_unique_id("entryclientid", 3) == "entryclientid:3"
