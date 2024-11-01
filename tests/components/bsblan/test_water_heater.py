"""Tests for the BSB-Lan water heater platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from bsblan import BSBLANError, StaticState
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    STATE_ECO,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.entity_registry as er

from . import setup_with_selected_platforms

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
    snapshot_platform,
)

ENTITY_ID = "water_heater.bsb_lan"


@pytest.fixture
def mock_bsblan_with_methods(mock_bsblan):
    """Create a mock with proper method signatures."""
    # Create an async mock for set_hot_water with the correct signature
    mock_bsblan.set_hot_water = AsyncMock()
    return mock_bsblan


@pytest.mark.parametrize(
    ("dhw_file"),
    [
        ("dhw_state.json"),
    ],
)
async def test_water_heater_states(
    hass: HomeAssistant,
    mock_bsblan_with_methods: AsyncMock,
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
    mock_bsblan_with_methods: AsyncMock,
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
    mock_bsblan_with_methods.hot_water_state.return_value.nominal_setpoint = (
        mock_setpoint
    )

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
    mock_bsblan_with_methods: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mode: str,
    bsblan_mode: str,
) -> None:
    """Test setting operation mode."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        "set_operation_mode",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "operation_mode": mode,
        },
        blocking=True,
    )

    mock_bsblan_with_methods.set_hot_water.assert_called_once_with(
        operating_mode=bsblan_mode
    )


async def test_set_invalid_operation_mode(
    hass: HomeAssistant,
    mock_bsblan_with_methods: AsyncMock,
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
            WATER_HEATER_DOMAIN,
            "set_operation_mode",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "operation_mode": "invalid_mode",
            },
            blocking=True,
        )


async def test_set_temperature(
    hass: HomeAssistant,
    mock_bsblan_with_methods: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting temperature."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        "set_temperature",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 50,
        },
        blocking=True,
    )

    mock_bsblan_with_methods.set_hot_water.assert_called_once_with(nominal_setpoint=50)


async def test_set_temperature_failure(
    hass: HomeAssistant,
    mock_bsblan_with_methods: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting temperature with API failure."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    mock_bsblan_with_methods.set_hot_water.side_effect = BSBLANError("Test error")

    with pytest.raises(
        HomeAssistantError, match="Failed to set target temperature for water heater"
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            "set_temperature",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 50,
            },
            blocking=True,
        )


async def test_operation_mode_error(
    hass: HomeAssistant,
    mock_bsblan_with_methods: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test operation mode setting with API failure."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    mock_bsblan_with_methods.set_hot_water.side_effect = BSBLANError("Test error")

    with pytest.raises(
        HomeAssistantError, match="Failed to set operation mode for water heater"
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            "set_operation_mode",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "operation_mode": STATE_ECO,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("static_file"),
    [
        ("static.json"),
        ("static_F.json"),
    ],
)
async def test_temperature_unit(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    static_file: str,
) -> None:
    """Test Celsius and Fahrenheit temperature units."""

    static_data = load_json_object_fixture(static_file, DOMAIN)

    mock_bsblan.static_values.return_value = StaticState.from_dict(static_data)

    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
