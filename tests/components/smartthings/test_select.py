"""Test for the SmartThings select platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
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

from tests.common import MockConfigEntry


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SELECT)


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.dryer").state == "stop"

    await trigger_update(
        hass,
        devices,
        "02f7256e-8353-5bdd-547f-bd5b1647e01b",
        Capability.DRYER_OPERATING_STATE,
        Attribute.MACHINE_STATE,
        "run",
    )

    assert hass.states.get("select.dryer").state == "run"


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_select_option(
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
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.dryer", ATTR_OPTION: "run"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "02f7256e-8353-5bdd-547f-bd5b1647e01b",
        Capability.DRYER_OPERATING_STATE,
        Command.SET_MACHINE_STATE,
        MAIN,
        argument="run",
    )


@pytest.mark.parametrize("device_fixture", ["da_ks_range_0101x"])
async def test_select_option_map(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.vulcan_lamp")
    assert state
    assert state.state == "extra_high"
    assert state.attributes[ATTR_OPTIONS] == [
        "off",
        "extra_high",
    ]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.vulcan_lamp", ATTR_OPTION: "extra_high"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "2c3cbaa0-1899-5ddc-7b58-9d657bd48f18",
        Capability.SAMSUNG_CE_LAMP,
        Command.SET_BRIGHTNESS_LEVEL,
        MAIN,
        argument="extraHigh",
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_select_option_without_remote_control(
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
        match="Can only be updated when remote control is enabled",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.dryer", ATTR_OPTION: "run"},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.dryer").state == "stop"

    await trigger_health_update(
        hass, devices, "02f7256e-8353-5bdd-547f-bd5b1647e01b", HealthStatus.OFFLINE
    )

    assert hass.states.get("select.dryer").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "02f7256e-8353-5bdd-547f-bd5b1647e01b", HealthStatus.ONLINE
    )

    assert hass.states.get("select.dryer").state == "stop"


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("select.dryer").state == STATE_UNAVAILABLE
