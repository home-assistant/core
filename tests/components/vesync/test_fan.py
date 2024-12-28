"""Tests for the fan module."""

import pytest
import requests_mock
from syrupy import SnapshotAssertion

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.vesync import DOMAIN, VS_COORDINATOR
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import (
    ALL_DEVICE_NAMES,
    mock_air_purifier_400s_update_response,
    mock_devices_response,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_fan_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    requests_mock: requests_mock.Mocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    # Configure the API devices call for device_name
    mock_devices_response(requests_mock, device_name)

    # setup platform - only including the named device
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][VS_COORDINATOR]
    assert coordinator

    # Check device registry
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    # Check entity registry
    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == FAN_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)

    # Test for update via coordinator using entity air_purifier_400s
    # Update the request mock to return different data
    mock_air_purifier_400s_update_response(requests_mock)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    for entity in entities:
        if entity.entity_id == "fan.air_purifier_400s":
            assert hass.states.get(entity.entity_id) == snapshot(
                name=f"{entity.entity_id}_updated"
            )
