"""Test the Frontier Silicon init flow."""

import logging
from typing import TypeVar
from unittest.mock import patch

from homeassistant.components.frontier_silicon.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import FakeAFSAPIDevice

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

V = TypeVar("V", bound=str | int)
ListValue = TypeVar("ListValue")


async def test_device_in_dr(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test Frontier Silicon device registry data."""
    with patch(
        "homeassistant.components.frontier_silicon.AFSAPI",
        FakeAFSAPIDevice,
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        devices = dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        )

        assert len(devices) == 1
        device_entry = devices[0]
        assert DOMAIN in [
            id_entry
            for id_tuple in list(device_entry.identifiers)
            for id_entry in id_tuple
        ]


async def test_entities_in_er(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the expected number of entities are created."""
    with patch(
        "homeassistant.components.frontier_silicon.AFSAPI",
        FakeAFSAPIDevice,
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        devices = dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        )

        assert len(devices) == 1
        device_entry = devices[0]

        expected_num_entities = 1
        entities = er.async_entries_for_device(entity_registry, device_entry.id)
        assert len(entities) == expected_num_entities
