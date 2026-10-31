"""Test the my-PV climate platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

from my_pv import MyPVDeviceMainMode
from my_pv.exceptions import (
    MyPVAuthenticationError,
    MyPVConnectionError,
    MyPVTooManyRequestsError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er


@pytest.fixture
def setup_configuration(setup_configuration: dict[str, Any]) -> dict[str, Any]:
    """Return a setup configuration with a room heating target temperature."""
    return {
        **setup_configuration,
        "rh1_target": {"step": 0.5, "unit": "°C", "min": 5.0, "max": 30.0},
    }


@pytest.fixture
def mock_my_pv_client(mock_my_pv_client: AsyncMock) -> AsyncMock:
    """Return a client in room heating mode."""
    mock_my_pv_client.primary_mode = MyPVDeviceMainMode.SPACE_HEATING
    mock_my_pv_client.current_temperature = 20.5
    mock_my_pv_client.target_temperature = 21.0
    return mock_my_pv_client


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up the my-PV integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_my_pv_client")
async def test_climate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful setup of a climate entity."""
    with patch("homeassistant.components.my_pv.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_climate_no_temp_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test that no climate entity is created without a temperature sensor."""
    mock_my_pv_client.current_temperature = None

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("climate.my_pv_ac_elwa_2") is None


async def test_climate_unavailable_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test if a climate entity is unavailable when not connected."""
    mock_my_pv_client.connected = False

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.my_pv_ac_elwa_2")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("service", "service_data", "method", "is_on", "expected_state"),
    [
        (SERVICE_TURN_OFF, {}, "turn_off", False, HVACMode.OFF),
        (SERVICE_TURN_ON, {}, "turn_on", True, HVACMode.HEAT),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            "turn_off",
            False,
            HVACMode.OFF,
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            "turn_on",
            True,
            HVACMode.HEAT,
        ),
    ],
)
async def test_climate_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    service: str,
    service_data: dict[str, Any],
    method: str,
    is_on: bool,
    expected_state: HVACMode,
) -> None:
    """Test turning the climate entity on and off."""
    mock_my_pv_client.is_on = not is_on

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.my_pv_ac_elwa_2")
    assert state.state == (HVACMode.HEAT if not is_on else HVACMode.OFF)

    mock_my_pv_client.is_on = is_on

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "climate.my_pv_ac_elwa_2", **service_data},
        blocking=True,
    )
    getattr(mock_my_pv_client, method).assert_awaited_once_with()

    state = hass.states.get("climate.my_pv_ac_elwa_2")
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "method", "is_on"),
    [
        (SERVICE_TURN_OFF, "turn_off", True),
        (SERVICE_TURN_ON, "turn_on", False),
    ],
)
async def test_climate_turn_on_off_returns_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    service: str,
    method: str,
    is_on: bool,
) -> None:
    """Test for HomeAssistantError when turning on or off returns False."""
    mock_my_pv_client.is_on = is_on

    await setup_integration(hass, mock_config_entry)

    setattr(mock_my_pv_client, method, AsyncMock(return_value=False))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "climate.my_pv_ac_elwa_2"},
            blocking=True,
        )
    getattr(mock_my_pv_client, method).assert_awaited_once_with()

    state = hass.states.get("climate.my_pv_ac_elwa_2")
    assert state.state == (HVACMode.HEAT if is_on else HVACMode.OFF)


async def test_climate_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test setting the target temperature."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.my_pv_ac_elwa_2")
    assert state.attributes[ATTR_TEMPERATURE] == 21.0
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.5

    mock_my_pv_client.target_temperature = 22.5

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.my_pv_ac_elwa_2", ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )
    mock_my_pv_client.set_target_temperature.assert_awaited_once_with(22.5)

    state = hass.states.get("climate.my_pv_ac_elwa_2")
    assert state.attributes[ATTR_TEMPERATURE] == 22.5


async def test_climate_set_temperature_returns_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test for HomeAssistantError when setting the temperature returns False."""
    await setup_integration(hass, mock_config_entry)

    mock_my_pv_client.set_target_temperature = AsyncMock(return_value=False)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.my_pv_ac_elwa_2", ATTR_TEMPERATURE: 22.5},
            blocking=True,
        )
    mock_my_pv_client.set_target_temperature.assert_awaited_once_with(22.5)

    state = hass.states.get("climate.my_pv_ac_elwa_2")
    assert state.attributes[ATTR_TEMPERATURE] == 21.0


@pytest.mark.parametrize(
    ("error", "expected_ha_error"),
    [
        (MyPVConnectionError(), HomeAssistantError),
        (MyPVAuthenticationError(), ConfigEntryAuthFailed),
        (MyPVTooManyRequestsError(), HomeAssistantError),
    ],
)
async def test_climate_set_temperature_raises_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
    error: MyPVConnectionError | MyPVAuthenticationError,
    expected_ha_error: type[HomeAssistantError],
) -> None:
    """Test setting the target temperature raises an error."""
    await setup_integration(hass, mock_config_entry)

    mock_my_pv_client.set_target_temperature.side_effect = error

    with pytest.raises(expected_ha_error):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.my_pv_ac_elwa_2", ATTR_TEMPERATURE: 22.5},
            blocking=True,
        )
    mock_my_pv_client.set_target_temperature.assert_awaited_once_with(22.5)

    state = hass.states.get("climate.my_pv_ac_elwa_2")
    assert state.attributes[ATTR_TEMPERATURE] == 21.0
