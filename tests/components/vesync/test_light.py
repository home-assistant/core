"""Tests for the light module."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, ENTITY_LIGHT, mock_devices_response

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
    ("action", "command"),
    [
        (SERVICE_TURN_ON, "pyvesync.devices.vesyncbulb.VeSyncBulbESL100CW.turn_on"),
        (SERVICE_TURN_OFF, "pyvesync.devices.vesyncbulb.VeSyncBulbESL100CW.turn_off"),
    ],
)
@pytest.mark.parametrize("device_config_entry", ["Temperature Light"], indirect=True)
async def test_turn_on_off_success(
    hass: HomeAssistant,
    device_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    action: str,
    command: str,
) -> None:
    """Test turn_on and turn_off method."""

    with (
        patch(command, new_callable=AsyncMock, return_value=True) as method_mock,
        patch(
            "homeassistant.components.vesync.light.VeSyncBaseLightHA.async_write_ha_state"
        ) as update_mock,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            action,
            {ATTR_ENTITY_ID: ENTITY_LIGHT},
            blocking=True,
        )

    await hass.async_block_till_done()
    method_mock.assert_called_once()
    update_mock.assert_called_once()


@pytest.mark.parametrize(
    ("action", "command"),
    [
        (
            SERVICE_TURN_ON,
            "pyvesync.base_devices.vesyncbasedevice.VeSyncBaseToggleDevice.turn_on",
        ),
        (
            SERVICE_TURN_OFF,
            "pyvesync.base_devices.vesyncbasedevice.VeSyncBaseToggleDevice.turn_off",
        ),
    ],
)
@pytest.mark.parametrize("device_config_entry", ["Temperature Light"], indirect=True)
async def test_turn_on_off_raises_error(
    hass: HomeAssistant,
    device_config_entry: MockConfigEntry,
    action: str,
    command: str,
) -> None:
    """Test turn_on and turn_off raises errors when fails."""

    # returns False indicating failure in which case raises HomeAssistantError.
    with (
        patch(
            command,
            return_value=False,
        ) as method_mock,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            action,
            {ATTR_ENTITY_ID: ENTITY_LIGHT},
            blocking=True,
        )

    await hass.async_block_till_done()
    method_mock.assert_called_once()
