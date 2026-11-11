"""Tests for the switch module."""

from contextlib import nullcontext
from unittest.mock import PropertyMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pyvesync.devices.vesynchumidifier import VeSyncHumid200S
from pyvesync.utils.errors import ResponseInfo
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, ENTITY_SWITCH_DISPLAY, mock_devices_response

NoException = nullcontext()
DEVICE_ERROR = ResponseInfo(name="error", error_type="error", message="Device error")


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
    ("action", "last_response", "message"),
    [
        pytest.param(
            SERVICE_TURN_ON, DEVICE_ERROR, "Device error", id="on_last_response"
        ),
        pytest.param(
            SERVICE_TURN_ON,
            None,
            "Unknown error turning on device, no response.",
            id="on_no_last_response",
        ),
        pytest.param(
            SERVICE_TURN_OFF, DEVICE_ERROR, "Device error", id="off_last_response"
        ),
        pytest.param(
            SERVICE_TURN_OFF,
            None,
            "Unknown error turning off device, no response.",
            id="off_no_last_response",
        ),
    ],
)
async def test_turn_on_off_display_raises_error(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    action: str,
    last_response: ResponseInfo | None,
    message: str,
) -> None:
    """Test switch turn on and off command raises HomeAssistantError."""

    mock_devices_response(aioclient_mock, "Humidifier 200s")

    async def _fail_toggle(device: VeSyncHumid200S, toggle: bool) -> bool:
        device.last_response = last_response
        return False

    with (
        patch.object(
            VeSyncHumid200S,
            "toggle_display",
            autospec=True,
            side_effect=_fail_toggle,
        ) as method_mock,
        pytest.raises(HomeAssistantError, match=message),
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
    ("device_name", "entity_id", "action", "command", "message"),
    [
        pytest.param(
            "Outlet",
            "switch.outlet",
            SERVICE_TURN_ON,
            "pyvesync.devices.vesyncoutlet.VeSyncOutlet.turn_on",
            "Device does not support toggling power.",
            id="power_on",
        ),
        pytest.param(
            "Outlet",
            "switch.outlet",
            SERVICE_TURN_OFF,
            "pyvesync.devices.vesyncoutlet.VeSyncOutlet.turn_off",
            "Device does not support toggling power.",
            id="power_off",
        ),
        pytest.param(
            "Humidifier 200s",
            "switch.humidifier_200s_display",
            SERVICE_TURN_ON,
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200S.toggle_display",
            "Device does not support toggling display.",
            id="display",
        ),
        pytest.param(
            "Humidifier 6000s",
            "switch.humidifier_6000s_child_lock",
            SERVICE_TURN_ON,
            "pyvesync.devices.vesynchumidifier.VeSyncSuperior6000S.toggle_child_lock",
            "Device does not support toggling child lock.",
            id="child_lock",
        ),
        pytest.param(
            "Humidifier 200s",
            "switch.humidifier_200s_auto_off",
            SERVICE_TURN_ON,
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200S.toggle_automatic_stop",
            "Device does not support toggling automatic stop.",
            id="auto_stop",
        ),
        pytest.param(
            "Humidifier 6000s",
            "switch.humidifier_6000s_enable_drying_mode_while_power_is_off",
            SERVICE_TURN_ON,
            "pyvesync.devices.vesynchumidifier.VeSyncSuperior6000S.toggle_drying_mode",
            "Device does not support toggling drying mode.",
            id="drying_mode",
        ),
    ],
)
async def test_switch_unsupported_command(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
    entity_id: str,
    action: str,
    command: str,
    message: str,
) -> None:
    """Test an error is raised when the device lacks the switch command."""
    mock_devices_response(aioclient_mock, device_name)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # hasattr() is False when attribute lookup raises AttributeError
    with (
        patch(command, new_callable=PropertyMock, side_effect=AttributeError),
        pytest.raises(HomeAssistantError, match=message),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            action,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


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
