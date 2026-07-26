"""Tests for the switch module."""

from contextlib import nullcontext
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, ENTITY_SWITCH_DISPLAY, mock_devices_response

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

NoException = nullcontext()


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_switch_state(
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
        if entity.domain == SWITCH_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.parametrize(
    ("action", "command"),
    [
        (
            SERVICE_TURN_ON,
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200S.toggle_display",
        ),
        (
            SERVICE_TURN_OFF,
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200S.toggle_display",
        ),
    ],
)
async def test_turn_on_off_display_raises_error(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    action: str,
    command: str,
) -> None:
    """Test switch turn on and off command raises HomeAssistantError."""

    mock_devices_response(aioclient_mock, "Humidifier 200s")

    with (
        patch(
            command,
            return_value=False,
        ) as method_mock,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            action,
            {ATTR_ENTITY_ID: ENTITY_SWITCH_DISPLAY},
            blocking=True,
        )

    await hass.async_block_till_done()
    method_mock.assert_called_once()


@pytest.mark.parametrize(
    ("device_name", "entity_id", "action", "command"),
    [
        # device_status switch for outlet
        (
            "Outlet",
            "switch.outlet",
            SERVICE_TURN_ON,
            "pyvesync.devices.vesyncoutlet.VeSyncOutlet.turn_on",
        ),
        (
            "Outlet",
            "switch.outlet",
            SERVICE_TURN_OFF,
            "pyvesync.devices.vesyncoutlet.VeSyncOutlet.turn_off",
        ),
        # display switch for humidifier
        (
            "Humidifier 200s",
            "switch.humidifier_200s_display",
            SERVICE_TURN_ON,
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200S.toggle_display",
        ),
        (
            "Humidifier 200s",
            "switch.humidifier_200s_display",
            SERVICE_TURN_OFF,
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200S.toggle_display",
        ),
        # auto_off_config switch for humidifier
        (
            "Humidifier 200s",
            "switch.humidifier_200s_auto_off",
            SERVICE_TURN_ON,
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200S.toggle_automatic_stop",
        ),
        (
            "Humidifier 200s",
            "switch.humidifier_200s_auto_off",
            SERVICE_TURN_OFF,
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200S.toggle_automatic_stop",
        ),
        # child_lock switch for humidifier
        (
            "Humidifier 6000s",
            "switch.humidifier_6000s_child_lock",
            SERVICE_TURN_ON,
            "pyvesync.devices.vesynchumidifier.VeSyncSuperior6000S.toggle_child_lock",
        ),
        (
            "Humidifier 6000s",
            "switch.humidifier_6000s_child_lock",
            SERVICE_TURN_OFF,
            "pyvesync.devices.vesynchumidifier.VeSyncSuperior6000S.toggle_child_lock",
        ),
        # drying_mode_power_off switch for humidifier with drying mode
        (
            "Humidifier 6000s",
            "switch.humidifier_6000s_enable_drying_mode_while_power_is_off",
            SERVICE_TURN_ON,
            "pyvesync.devices.vesynchumidifier.VeSyncSuperior6000S.toggle_drying_mode",
        ),
        (
            "Humidifier 6000s",
            "switch.humidifier_6000s_enable_drying_mode_while_power_is_off",
            SERVICE_TURN_OFF,
            "pyvesync.devices.vesynchumidifier.VeSyncSuperior6000S.toggle_drying_mode",
        ),
    ],
)
async def test_switch_operations(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
    entity_id: str,
    action: str,
    command: str,
) -> None:
    """Test all switch operations with appropriate devices and parameters."""

    # Configure the API devices call for the specific device
    mock_devices_response(aioclient_mock, device_name)

    # Setup platform
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(
            command,
            return_value=True,
        ) as method_mock,
        patch(
            "homeassistant.components.vesync.switch.VeSyncSwitchEntity.async_write_ha_state"
        ) as update_mock,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            action,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    await hass.async_block_till_done()
    method_mock.assert_called_once()
    update_mock.assert_called_once()
