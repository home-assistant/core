"""Test for the SmartThings button platform."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.smartthings import MAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import (
    set_attribute_value,
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.BUTTON)


@pytest.mark.parametrize("device_fixture", ["da_ks_microwave_0101x"])
async def test_press(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)
    freezer.move_to("2023-10-21")

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.theater_microwave_stop"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "2bad3237-4886-e699-1b90-4a51a3d55c8a",
        Capability.OVEN_OPERATING_STATE,
        Command.STOP,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["da_ks_microwave_0101x"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("button.theater_microwave_stop").state == STATE_UNKNOWN

    await trigger_health_update(
        hass, devices, "2bad3237-4886-e699-1b90-4a51a3d55c8a", HealthStatus.OFFLINE
    )

    assert hass.states.get("button.theater_microwave_stop").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "2bad3237-4886-e699-1b90-4a51a3d55c8a", HealthStatus.ONLINE
    )

    assert hass.states.get("button.theater_microwave_stop").state == STATE_UNKNOWN


@pytest.mark.parametrize("device_fixture", ["da_ks_microwave_0101x"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("button.theater_microwave_stop").state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_turn_on_without_remote_control(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "false",
    )
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError,
        match="Can only be changed when remote control is enabled",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.dishwasher_1_start"},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_turn_on_with_wrong_dishwasher_machine_state(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    set_attribute_value(
        devices,
        Capability.DISHWASHER_OPERATING_STATE,
        Attribute.MACHINE_STATE,
        "run",
    )
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError,
        match="Can only be changed when the dishwasher machine state is stop",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.dishwasher_1_start"},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()


DISHWASHER_START_LATER_ENTITY_ID = "button.dishwasher_1_start_later"


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_press_dishwasher_start_later(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test starting the dishwasher later sends the delay in seconds."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    set_attribute_value(
        devices,
        Capability.CUSTOM_DISHWASHER_DELAY_START_TIME,
        Attribute.DISHWASHER_DELAY_START_TIME,
        "08:08:00",
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: DISHWASHER_START_LATER_ENTITY_ID},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "7ff318f3-3772-524d-3c9f-72fcd26413ed",
        Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
        Command.START_LATER,
        MAIN,
        argument=29280,
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
@pytest.mark.parametrize(
    ("remote_control_enabled", "machine_state", "delay_start_time", "message"),
    [
        pytest.param(
            "false",
            "stop",
            "08:08:00",
            "Can only be changed when remote control is enabled",
            id="remote_control_disabled",
        ),
        pytest.param(
            "true",
            "run",
            "08:08:00",
            "Can only be changed when the dishwasher machine state is stop",
            id="machine_running",
        ),
        pytest.param(
            "true",
            "stop",
            "00:00:00",
            "Set a delay start time before starting the dishwasher later",
            id="no_delay",
        ),
        pytest.param(
            "true",
            "stop",
            None,
            "Set a delay start time before starting the dishwasher later",
            id="unknown_delay",
        ),
    ],
)
async def test_press_dishwasher_start_later_not_allowed(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    remote_control_enabled: str,
    machine_state: str,
    delay_start_time: str | None,
    message: str,
) -> None:
    """Test starting the dishwasher later is validated."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        remote_control_enabled,
    )
    set_attribute_value(
        devices,
        Capability.DISHWASHER_OPERATING_STATE,
        Attribute.MACHINE_STATE,
        machine_state,
    )
    set_attribute_value(
        devices,
        Capability.CUSTOM_DISHWASHER_DELAY_START_TIME,
        Attribute.DISHWASHER_DELAY_START_TIME,
        delay_start_time,
    )
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match=message):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: DISHWASHER_START_LATER_ENTITY_ID},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()
