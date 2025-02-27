"""Tests for the BSB-Lan water heater platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from bsblan import BSBLANError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_ECO,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "water_heater.bsb_lan"


@pytest.mark.parametrize(
    ("dhw_file"),
    [
        ("dhw_state.json"),
    ],
)
async def test_water_heater_states(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    dhw_file: str,
) -> None:
    """Test water heater states with different configurations."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_water_heater_entity_properties(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the water heater entity properties."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None

    # Test when nominal setpoint is "10"
    mock_setpoint = MagicMock()
    mock_setpoint.value = 10
    mock_bsblan.hot_water_state.return_value.nominal_setpoint = mock_setpoint

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get("temperature") == 10


@pytest.mark.parametrize(
    ("mode", "bsblan_mode"),
    [
        (STATE_ECO, "Eco"),
        (STATE_OFF, "Off"),
        (STATE_ON, "On"),
    ],
)
async def test_set_operation_mode(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mode: str,
    bsblan_mode: str,
) -> None:
    """Test setting operation mode."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    await hass.services.async_call(
        domain=WATER_HEATER_DOMAIN,
        service=SERVICE_SET_OPERATION_MODE,
        service_data={
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_OPERATION_MODE: mode,
        },
        blocking=True,
    )

    mock_bsblan.set_hot_water.assert_called_once_with(operating_mode=bsblan_mode)


async def test_set_invalid_operation_mode(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting invalid operation mode."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    with pytest.raises(
        HomeAssistantError,
        match=r"Operation mode invalid_mode is not valid for water_heater\.bsb_lan\. Valid operation modes are: eco, off, on",
    ):
        await hass.services.async_call(
            domain=WATER_HEATER_DOMAIN,
            service=SERVICE_SET_OPERATION_MODE,
            service_data={
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_OPERATION_MODE: "invalid_mode",
            },
            blocking=True,
        )


async def test_set_temperature(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting temperature."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    await hass.services.async_call(
        domain=WATER_HEATER_DOMAIN,
        service=SERVICE_SET_TEMPERATURE,
        service_data={
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 50,
        },
        blocking=True,
    )

    mock_bsblan.set_hot_water.assert_called_once_with(nominal_setpoint=50)


async def test_set_temperature_failure(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting temperature with API failure."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    mock_bsblan.set_hot_water.side_effect = BSBLANError("Test error")

    with pytest.raises(
        HomeAssistantError, match="An error occurred while setting the temperature"
    ):
        await hass.services.async_call(
            domain=WATER_HEATER_DOMAIN,
            service=SERVICE_SET_TEMPERATURE,
            service_data={
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 50,
            },
            blocking=True,
        )


async def test_operation_mode_error(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test operation mode setting with API failure."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    mock_bsblan.set_hot_water.side_effect = BSBLANError("Test error")

    with pytest.raises(
        HomeAssistantError, match="An error occurred while setting the operation mode"
    ):
        await hass.services.async_call(
            domain=WATER_HEATER_DOMAIN,
            service=SERVICE_SET_OPERATION_MODE,
            service_data={
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_OPERATION_MODE: STATE_ECO,
            },
            blocking=True,
        )
