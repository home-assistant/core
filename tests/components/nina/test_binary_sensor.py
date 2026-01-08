"""Test the Nina binary sensor."""

from __future__ import annotations

from typing import Any

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nina.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform

ENTRY_DATA: dict[str, Any] = {
    "slots": 5,
    "regions": {"083350000000": "Aach, Stadt"},
    "filters": {
        "headline_filter": ".*corona.*",
        "area_filter": ".*",
    },
}

ENTRY_DATA_NO_CORONA: dict[str, Any] = {
    "slots": 5,
    "regions": {"083350000000": "Aach, Stadt"},
    "filters": {
        "headline_filter": "/(?!)/",
        "area_filter": ".*",
    },
}

ENTRY_DATA_NO_AREA: dict[str, Any] = {
    "slots": 5,
    "regions": {"083350000000": "Aach, Stadt"},
    "filters": {
        "headline_filter": "/(?!)/",
        "area_filter": ".*nagold.*",
    },
}


async def test_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test the creation and values of the NINA sensors."""

    conf_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN, title="NINA", data=ENTRY_DATA, version=1, minor_version=3
    )
    conf_entry.add_to_hass(hass)

    await setup_platform(hass, conf_entry)

    await snapshot_platform(hass, entity_registry, snapshot, conf_entry.entry_id)


async def test_sensors_without_corona_filter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test the creation and values of the NINA sensors without the corona filter."""

    conf_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=ENTRY_DATA_NO_CORONA,
        version=1,
        minor_version=3,
    )
    conf_entry.add_to_hass(hass)

    await setup_platform(hass, conf_entry)

    await snapshot_platform(hass, entity_registry, snapshot, conf_entry.entry_id)


async def test_sensors_with_area_filter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test the creation and values of the NINA sensors with an area filter."""

    conf_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=ENTRY_DATA_NO_AREA,
        version=1,
        minor_version=3,
    )
    conf_entry.add_to_hass(hass)

    await setup_platform(hass, conf_entry)

    await snapshot_platform(hass, entity_registry, snapshot, conf_entry.entry_id)
