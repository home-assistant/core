"""Tests for the light module."""

from contextlib import nullcontext
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, mock_devices_response

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_light_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    # Configure the API devices call for device_name
    mock_devices_response(aioclient_mock, device_name)

    # setup platform - only including the named device
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check device registry
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    # Check entity registry
    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == LIGHT_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(True, nullcontext()), (False, pytest.raises(HomeAssistantError))],
)
async def test_brightness_change(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    api_response: bool,
    expectation,
) -> None:
    """Test a brightness change holds the device on success and raises on failure."""
    mock_devices_response(aioclient_mock, "Dimmable Light")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        expectation,
        patch(
            "pyvesync.devices.vesyncbulb.VeSyncBulbESL100.set_brightness",
            return_value=api_response,
        ) as method_mock,
        patch(
            "homeassistant.components.vesync.coordinator.VeSyncDataCoordinator.async_mark_command"
        ) as mark_mock,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.dimmable_light", ATTR_BRIGHTNESS: 128},
            blocking=True,
        )

    method_mock.assert_called_once()
    assert mark_mock.call_count == int(api_response)


async def test_partial_attribute_change_holds_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a half-failed attribute change raises but still holds the device."""
    mock_devices_response(aioclient_mock, "Temperature Light")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(
            "pyvesync.devices.vesyncbulb.VeSyncBulbESL100CW.set_color_temp",
            return_value=False,
        ),
        patch(
            "pyvesync.devices.vesyncbulb.VeSyncBulbESL100CW.set_brightness",
            return_value=True,
        ),
        patch(
            "homeassistant.components.vesync.coordinator.VeSyncDataCoordinator.async_mark_command"
        ) as mark_mock,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.temperature_light",
                ATTR_BRIGHTNESS: 128,
                ATTR_COLOR_TEMP_KELVIN: 3000,
            },
            blocking=True,
        )

    mark_mock.assert_called_once()
