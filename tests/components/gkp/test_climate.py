"""Tests for the GKP climate platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from gkphomepython import (
    USER_CONNECTED_REPORT_DELAY,
    GkpConnectionError,
    GkpMode,
    GkpRateLimitError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACAction,
    HVACMode,
)
from homeassistant.components.gkp.const import FAST_POLLING_INTERVAL, PRESET_DEFROST
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import advance_time, setup_integration
from .conftest import (
    BEDROOM_ENTITY_ID,
    BEDROOM_ID,
    LIVING_ROOM_ENTITY_ID,
    LIVING_ROOM_ID,
)


@pytest.mark.usefixtures("mock_gkp_client")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the climate entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("mode", "heating", "expected_state", "expected_attributes"),
    [
        pytest.param(
            GkpMode.OFF.value,
            1,
            HVACMode.OFF,
            {
                ATTR_HVAC_ACTION: HVACAction.OFF,
                ATTR_PRESET_MODE: None,
                ATTR_TEMPERATURE: None,
            },
            id="off",
        ),
        pytest.param(
            GkpMode.ECO.value,
            0,
            HVACMode.HEAT,
            {
                ATTR_HVAC_ACTION: HVACAction.IDLE,
                ATTR_PRESET_MODE: PRESET_ECO,
                ATTR_TEMPERATURE: 22.0,
            },
            id="eco",
        ),
        pytest.param(
            GkpMode.AUTO.value,
            1,
            HVACMode.AUTO,
            {
                ATTR_HVAC_ACTION: HVACAction.HEATING,
                ATTR_PRESET_MODE: None,
                ATTR_TEMPERATURE: 22.0,
            },
            id="auto",
        ),
        pytest.param(
            GkpMode.DEFROST.value,
            0,
            HVACMode.HEAT,
            {
                ATTR_HVAC_ACTION: HVACAction.IDLE,
                ATTR_PRESET_MODE: PRESET_DEFROST,
                ATTR_TEMPERATURE: 22.0,
            },
            id="defrost",
        ),
        pytest.param(
            GkpMode.BOOST.value,
            1,
            HVACMode.HEAT,
            {
                ATTR_HVAC_ACTION: HVACAction.HEATING,
                ATTR_PRESET_MODE: PRESET_BOOST,
                ATTR_TEMPERATURE: 22.0,
            },
            id="boost",
        ),
        pytest.param(
            None,
            1,
            STATE_UNKNOWN,
            {
                ATTR_HVAC_ACTION: None,
                ATTR_PRESET_MODE: None,
                ATTR_TEMPERATURE: 22.0,
            },
            id="unknown",
        ),
    ],
)
@pytest.mark.usefixtures("mock_gkp_client")
async def test_mode_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_contents: dict[str, dict[str, Any]],
    mode: int | None,
    heating: int,
    expected_state: str,
    expected_attributes: dict[str, Any],
) -> None:
    """Test the state of the entity in each device mode."""
    device_contents[LIVING_ROOM_ID]["Cm"]["value"] = mode
    device_contents[LIVING_ROOM_ID]["Hs"]["value"] = heating

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.1
    assert {
        key: state.attributes.get(key) for key in expected_attributes
    } == expected_attributes


@pytest.mark.parametrize(
    ("entity_id", "device_id", "temperature", "mode"),
    [
        pytest.param(
            LIVING_ROOM_ENTITY_ID, LIVING_ROOM_ID, 23.5, GkpMode.COMFORT, id="comfort"
        ),
        pytest.param(
            BEDROOM_ENTITY_ID, BEDROOM_ID, 25.0, GkpMode.AUTO, id="auto_boost"
        ),
    ],
)
async def test_set_temperature(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    device_id: str,
    temperature: float,
    mode: GkpMode,
) -> None:
    """Test setting the temperature sends the current mode to the library."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: temperature},
        blocking=True,
    )

    mock_gkp_client.set_temperature.assert_called_once_with(
        device_id, mode, temperature
    )


async def test_set_temperature_with_heat_hvac_mode(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_contents: dict[str, dict[str, Any]],
) -> None:
    """Test setting the temperature of an off device with the heat HVAC mode."""
    device_contents[LIVING_ROOM_ID]["Cm"]["value"] = GkpMode.OFF.value
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID,
            ATTR_TEMPERATURE: 21.0,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    mock_gkp_client.set_temperature.assert_called_once_with(
        LIVING_ROOM_ID, GkpMode.COMFORT, 21.0
    )


@pytest.mark.parametrize(
    ("hvac_mode", "translation_key"),
    [
        pytest.param(HVACMode.OFF, "setpoint_not_adjustable", id="off"),
        pytest.param(HVACMode.AUTO, "setpoint_not_adjustable", id="auto"),
        pytest.param(HVACMode.COOL, "not_valid_hvac_mode", id="unsupported"),
    ],
)
async def test_set_temperature_with_hvac_mode_not_adjustable(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode: HVACMode,
    translation_key: str,
) -> None:
    """Test the temperature cannot be set with an invalid HVAC mode."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID,
                ATTR_TEMPERATURE: 21.0,
                ATTR_HVAC_MODE: hvac_mode,
            },
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    mock_gkp_client.set_mode.assert_not_called()
    mock_gkp_client.set_temperature.assert_not_called()


@pytest.mark.parametrize(
    ("mode", "temperature"),
    [
        pytest.param(GkpMode.OFF.value, 20.0, id="off"),
        pytest.param(GkpMode.DEFROST.value, 7.0, id="defrost"),
        pytest.param(None, 20.0, id="unknown"),
    ],
)
async def test_set_temperature_not_adjustable(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_contents: dict[str, dict[str, Any]],
    mode: int | None,
    temperature: float,
) -> None:
    """Test the temperature cannot be set in modes without adjustable setpoint."""
    device_contents[LIVING_ROOM_ID]["Cm"]["value"] = mode
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, ATTR_TEMPERATURE: temperature},
            blocking=True,
        )

    assert err.value.translation_key == "setpoint_not_adjustable"
    mock_gkp_client.set_temperature.assert_not_called()


@pytest.mark.parametrize(
    ("service", "data", "mode"),
    [
        pytest.param(
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            GkpMode.COMFORT,
            id="heat",
        ),
        pytest.param(
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.AUTO},
            GkpMode.AUTO,
            id="auto",
        ),
        pytest.param(
            SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.OFF}, GkpMode.OFF, id="off"
        ),
        pytest.param(SERVICE_TURN_OFF, {}, GkpMode.OFF, id="turn_off"),
        pytest.param(
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_ECO},
            GkpMode.ECO,
            id="eco",
        ),
        pytest.param(
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_COMFORT},
            GkpMode.COMFORT,
            id="comfort",
        ),
        pytest.param(
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_BOOST},
            GkpMode.BOOST,
            id="boost",
        ),
        pytest.param(
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_DEFROST},
            GkpMode.DEFROST,
            id="defrost",
        ),
    ],
)
async def test_set_mode(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    data: dict[str, Any],
    mode: GkpMode,
) -> None:
    """Test HVAC modes and presets are mapped to device modes."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, **data},
        blocking=True,
    )

    mock_gkp_client.set_mode.assert_called_once_with(LIVING_ROOM_ID, mode)


async def test_turn_on(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_contents: dict[str, dict[str, Any]],
) -> None:
    """Test turning on a device that is off."""
    device_contents[LIVING_ROOM_ID]["Cm"]["value"] = GkpMode.OFF.value
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID},
        blocking=True,
    )

    mock_gkp_client.set_mode.assert_called_once_with(LIVING_ROOM_ID, GkpMode.COMFORT)


async def test_fast_polling(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_contents: dict[str, dict[str, Any]],
) -> None:
    """Test a command triggers fast polling that stops after a minute."""
    await setup_integration(hass, mock_config_entry)
    # Let the hub read the answer to the initial wake up first
    await advance_time(hass, freezer, USER_CONNECTED_REPORT_DELAY)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, ATTR_PRESET_MODE: PRESET_ECO},
        blocking=True,
    )
    device_contents[LIVING_ROOM_ID]["Cm"]["value"] = GkpMode.ECO.value
    mock_gkp_client.get_thermostat.reset_mock()

    await advance_time(hass, freezer, FAST_POLLING_INTERVAL)

    mock_gkp_client.get_thermostat.assert_called_once()
    assert mock_gkp_client.get_thermostat.call_args.args[0] == LIVING_ROOM_ID
    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_ECO

    # Fast polling ends after one minute
    await advance_time(hass, freezer, timedelta(minutes=1))
    mock_gkp_client.get_thermostat.reset_mock()

    await advance_time(hass, freezer, FAST_POLLING_INTERVAL)

    mock_gkp_client.get_thermostat.assert_not_called()


@pytest.mark.parametrize(
    ("service", "data", "client_method", "translation_key"),
    [
        pytest.param(
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 23.5},
            "set_temperature",
            "set_temperature_error",
            id="set_temperature",
        ),
        pytest.param(
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            "set_mode",
            "set_hvac_mode_error",
            id="set_hvac_mode",
        ),
        pytest.param(
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_ECO},
            "set_mode",
            "set_preset_mode_error",
            id="set_preset_mode",
        ),
    ],
)
async def test_command_error(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    data: dict[str, Any],
    client_method: str,
    translation_key: str,
) -> None:
    """Test API errors while sending a command."""
    await setup_integration(hass, mock_config_entry)
    getattr(mock_gkp_client, client_method).side_effect = GkpConnectionError("lost")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, **data},
            blocking=True,
        )

    assert err.value.translation_key == translation_key


async def test_command_rate_limited(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test commands tell the user when to try again when rate limited."""
    await setup_integration(hass, mock_config_entry)
    mock_gkp_client.set_temperature.side_effect = GkpRateLimitError("limited", 30)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, ATTR_TEMPERATURE: 23.5},
            blocking=True,
        )

    assert err.value.translation_key == "rate_limited"
    assert err.value.translation_placeholders == {"retry_after": "30"}
