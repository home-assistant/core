"""Test the Nina binary sensor."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nina.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import mocked_request_function

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

    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):
        conf_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN, title="NINA", data=ENTRY_DATA, version=1, minor_version=3
        )
        conf_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(conf_entry.entry_id)
        await hass.async_block_till_done()

        assert conf_entry.state is ConfigEntryState.LOADED

        await snapshot_platform(hass, entity_registry, snapshot, conf_entry.entry_id)


async def test_sensors_without_corona_filter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test the creation and values of the NINA sensors without the corona filter."""

    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):
        conf_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN,
            title="NINA",
            data=ENTRY_DATA_NO_CORONA,
            version=1,
            minor_version=3,
        )
        conf_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(conf_entry.entry_id)
        await hass.async_block_till_done()

        assert conf_entry.state is ConfigEntryState.LOADED

        await snapshot_platform(hass, entity_registry, snapshot, conf_entry.entry_id)


async def test_sensors_with_area_filter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test the creation and values of the NINA sensors with an area filter."""

    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):
        conf_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN,
            title="NINA",
            data=ENTRY_DATA_NO_AREA,
            version=1,
            minor_version=3,
        )
        conf_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(conf_entry.entry_id)
        await hass.async_block_till_done()

        assert conf_entry.state is ConfigEntryState.LOADED

        await snapshot_platform(hass, entity_registry, snapshot, conf_entry.entry_id)
