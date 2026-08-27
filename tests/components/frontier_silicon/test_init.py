"""Test the Frontier Silicon init flow."""

from unittest.mock import AsyncMock

from afsapi import FSConnectionError, FSNotImplementedError
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("dst_switch_side_effect", "expected_num_entities"),
    [(None, 2), (FSNotImplementedError, 1)],
)
async def test_init_with_dst_availability(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_afsapi: AsyncMock,
    dst_switch_side_effect: FSNotImplementedError | None,
    expected_num_entities: int,
) -> None:
    """Test integration setup notices the difference between devices which do or don't implement a DST switch."""
    mock_afsapi.get_dst.side_effect = dst_switch_side_effect

    await setup_integration(hass, config_entry)

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device_entry = devices[0]

    entities = er.async_entries_for_device(entity_registry, device_entry.id)
    assert len(entities) == expected_num_entities


async def test_init_device_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_afsapi: AsyncMock,
) -> None:
    """Test that entity isn't added if there is a connection error."""
    mock_afsapi.get_dst.side_effect = FSConnectionError

    await setup_integration(hass, config_entry)

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device_entry = devices[0]

    entities = er.async_entries_for_device(entity_registry, device_entry.id)
    expected_entities = 1
    assert len(entities) == expected_entities
