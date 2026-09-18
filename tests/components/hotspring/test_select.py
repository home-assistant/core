"""Tests for the Hot Spring select platform."""

from unittest.mock import MagicMock

from hotspring import (
    HeatingMode,
    HotSpringConnectionError,
    HotSpringError,
    Jet,
    JetSpeed,
    JetSpeedType,
    Spa,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

JET_1_ENTITY_ID = "select.connectedspa_ddeeff_jet_1"
HEATING_MODE_ENTITY_ID = "select.connectedspa_ddeeff_heating_mode"


async def test_select_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the select entities state."""
    device_fixture.jets[1].speed_type = JetSpeedType.DUAL_SPEED
    device_fixture.jets[2].speed_type = JetSpeedType.SINGLE_SPEED
    device_fixture.heater.heatpump_installed = True
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SELECT])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "option", "method_name", "expected_args"),
    [
        pytest.param(
            JET_1_ENTITY_ID,
            "high",
            "set_jet",
            (1, JetSpeed.HIGH_SPEED),
            id="jet_speed",
        ),
        pytest.param(
            HEATING_MODE_ENTITY_ID,
            "heat_with_boost",
            "set_heating_mode",
            (HeatingMode.HEAT_WITH_BOOST,),
            id="heating_mode",
        ),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
    entity_id: str,
    option: str,
    method_name: str,
    expected_args: tuple[object, ...],
) -> None:
    """Test selecting options for select entities."""
    device_fixture.jets[1].speed_type = JetSpeedType.DUAL_SPEED
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SELECT])

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    getattr(mock_hotspring, method_name).assert_called_once_with(*expected_args)


@pytest.mark.parametrize(
    ("exception", "match"),
    [
        (
            HotSpringConnectionError,
            "An error occurred while communicating with the Hot Spring API",
        ),
        (HotSpringError, "Invalid response received from the Hot Spring API"),
    ],
)
async def test_select_option_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    exception: type[Exception],
    match: str,
) -> None:
    """Test exception handling when changing select option."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SELECT])
    mock_hotspring.set_jet.side_effect = exception

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: JET_1_ENTITY_ID, ATTR_OPTION: "high"},
            blocking=True,
        )


async def test_unsupported_entities_not_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabled jet and unsupported heating mode are not added."""
    device_fixture.jets = {
        1: Jet(jet_id=1, speed=JetSpeed.OFF, is_enabled=False, on_seconds=0),
    }
    device_fixture.heater.heating_mode = HeatingMode.INVALID
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SELECT])

    assert not entity_registry.async_is_registered(JET_1_ENTITY_ID)
    assert not entity_registry.async_is_registered(HEATING_MODE_ENTITY_ID)
