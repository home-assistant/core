"""Test for the SmartThings number platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.smartthings import MAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import (
    set_attribute_value,
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
    trigger_update,
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

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.NUMBER)


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_set_value(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a value."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.theater_washer_rinse_cycles", ATTR_VALUE: 3},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "f984b91d-f250-9d42-3436-33f09a422a47",
        Capability.CUSTOM_WASHER_RINSE_CYCLES,
        Command.SET_WASHER_RINSE_CYCLES,
        MAIN,
        argument="3",
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.theater_washer_rinse_cycles").state == "2"

    await trigger_update(
        hass,
        devices,
        "f984b91d-f250-9d42-3436-33f09a422a47",
        Capability.CUSTOM_WASHER_RINSE_CYCLES,
        Attribute.WASHER_RINSE_CYCLES,
        "3",
    )

    assert hass.states.get("number.theater_washer_rinse_cycles").state == "3"


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.theater_washer_rinse_cycles").state == "2"

    await trigger_health_update(
        hass, devices, "f984b91d-f250-9d42-3436-33f09a422a47", HealthStatus.OFFLINE
    )

    assert (
        hass.states.get("number.theater_washer_rinse_cycles").state == STATE_UNAVAILABLE
    )

    await trigger_health_update(
        hass, devices, "f984b91d-f250-9d42-3436-33f09a422a47", HealthStatus.ONLINE
    )

    assert hass.states.get("number.theater_washer_rinse_cycles").state == "2"


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert (
        hass.states.get("number.theater_washer_rinse_cycles").state == STATE_UNAVAILABLE
    )


DISHWASHER_DELAY_START_ENTITY_ID = "number.dishwasher_1_delay_start"


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_dishwasher_delay_start_state(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the dishwasher delay start duration is converted to minutes."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(DISHWASHER_DELAY_START_ENTITY_ID).state == "0"

    await trigger_update(
        hass,
        devices,
        "7ff318f3-3772-524d-3c9f-72fcd26413ed",
        Capability.CUSTOM_DISHWASHER_DELAY_START_TIME,
        Attribute.DISHWASHER_DELAY_START_TIME,
        "08:08:00",
    )

    assert hass.states.get(DISHWASHER_DELAY_START_ENTITY_ID).state == "488"


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
@pytest.mark.parametrize(
    ("value", "argument"),
    [
        pytest.param(0, "00:00:00", id="zero"),
        pytest.param(488, "08:08:00", id="hours_and_minutes"),
        pytest.param(1440, "24:00:00", id="maximum"),
    ],
)
async def test_set_dishwasher_delay_start(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    value: int,
    argument: str,
) -> None:
    """Test setting the dishwasher delay start."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: DISHWASHER_DELAY_START_ENTITY_ID, ATTR_VALUE: value},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "7ff318f3-3772-524d-3c9f-72fcd26413ed",
        Capability.CUSTOM_DISHWASHER_DELAY_START_TIME,
        Command.SET_DISHWASHER_DELAY_START_TIME,
        MAIN,
        argument=argument,
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
@pytest.mark.parametrize(
    ("remote_control_enabled", "machine_state", "message"),
    [
        pytest.param(
            "false",
            "stop",
            "Can only be changed when remote control is enabled",
            id="remote_control_disabled",
        ),
        pytest.param(
            "true",
            "run",
            "Can only be changed when the dishwasher machine state is stop",
            id="machine_running",
        ),
    ],
)
async def test_set_dishwasher_delay_start_not_allowed(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    remote_control_enabled: str,
    machine_state: str,
    message: str,
) -> None:
    """Test the dishwasher delay start can only be set when allowed."""
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
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match=message):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: DISHWASHER_DELAY_START_ENTITY_ID, ATTR_VALUE: 60},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()
