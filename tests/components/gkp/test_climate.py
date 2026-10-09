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
from probatio import Invalid
import pytest
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
from homeassistant.components.gkp.const import (
    ATTR_DURATION,
    DOMAIN,
    FAST_POLLING_INTERVAL,
    PRESET_DEFROST,
    SERVICE_ACTIVATE_BOOST,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import BEDROOM_ID, LIVING_ROOM_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

LIVING_ROOM_ENTITY_ID = "climate.living_room"
BEDROOM_ENTITY_ID = "climate.bedroom"


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
    ("mode", "heating", "expected"),
    [
        pytest.param(
            0,
            1,
            {
                "state": HVACMode.OFF,
                ATTR_HVAC_ACTION: HVACAction.OFF,
                ATTR_PRESET_MODE: None,
                ATTR_TEMPERATURE: None,
            },
            id="off",
        ),
        pytest.param(
            1,
            0,
            {
                "state": HVACMode.HEAT,
                ATTR_HVAC_ACTION: HVACAction.IDLE,
                ATTR_PRESET_MODE: PRESET_ECO,
                ATTR_TEMPERATURE: 22.0,
            },
            id="eco",
        ),
        pytest.param(
            2,
            1,
            {
                "state": HVACMode.AUTO,
                ATTR_HVAC_ACTION: HVACAction.HEATING,
                ATTR_PRESET_MODE: None,
                ATTR_TEMPERATURE: 22.0,
            },
            id="auto",
        ),
        pytest.param(
            4,
            0,
            {
                "state": HVACMode.HEAT,
                ATTR_HVAC_ACTION: HVACAction.IDLE,
                ATTR_PRESET_MODE: PRESET_DEFROST,
                ATTR_TEMPERATURE: 22.0,
            },
            id="defrost",
        ),
        pytest.param(
            5,
            1,
            {
                "state": HVACMode.HEAT,
                ATTR_HVAC_ACTION: HVACAction.HEATING,
                ATTR_PRESET_MODE: PRESET_BOOST,
                ATTR_TEMPERATURE: 22.0,
            },
            id="boost",
        ),
        pytest.param(
            None,
            1,
            {
                "state": STATE_UNKNOWN,
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
    expected: dict[str, Any],
) -> None:
    """Test the state of the entity in each device mode."""
    device_contents[LIVING_ROOM_ID]["Cm"]["value"] = mode
    device_contents[LIVING_ROOM_ID]["Hs"]["value"] = heating

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.1
    assert {
        "state": state.state,
        **{key: state.attributes.get(key) for key in expected if key != "state"},
    } == expected


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


@pytest.mark.parametrize(
    ("mode", "temperature"),
    [
        pytest.param(0, 20.0, id="off"),
        pytest.param(4, 7.0, id="defrost"),
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


async def test_set_temperature_error(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an API error while setting the temperature."""
    await setup_integration(hass, mock_config_entry)
    mock_gkp_client.set_temperature.side_effect = GkpConnectionError("lost")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, ATTR_TEMPERATURE: 23.5},
            blocking=True,
        )

    assert err.value.translation_key == "set_temperature_error"


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
    device_contents[LIVING_ROOM_ID]["Cm"]["value"] = 0
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID},
        blocking=True,
    )

    mock_gkp_client.set_mode.assert_called_once_with(LIVING_ROOM_ID, GkpMode.COMFORT)


@pytest.mark.parametrize(
    ("service", "data", "translation_key"),
    [
        pytest.param(
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            "set_hvac_mode_error",
            id="hvac_mode",
        ),
        pytest.param(
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_ECO},
            "set_preset_mode_error",
            id="preset_mode",
        ),
    ],
)
async def test_set_mode_error(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    data: dict[str, Any],
    translation_key: str,
) -> None:
    """Test API errors while changing the mode."""
    await setup_integration(hass, mock_config_entry)
    mock_gkp_client.set_mode.side_effect = GkpConnectionError("lost")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, **data},
            blocking=True,
        )

    assert err.value.translation_key == translation_key


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
    freezer.tick(USER_CONNECTED_REPORT_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, ATTR_PRESET_MODE: PRESET_ECO},
        blocking=True,
    )
    device_contents[LIVING_ROOM_ID]["Cm"]["value"] = 1
    mock_gkp_client.get_thermostat.reset_mock()

    freezer.tick(FAST_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_gkp_client.get_thermostat.assert_called_once()
    assert mock_gkp_client.get_thermostat.call_args.args[0] == LIVING_ROOM_ID
    state = hass.states.get(LIVING_ROOM_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_ECO

    # Fast polling ends after one minute
    freezer.tick(timedelta(seconds=56))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_gkp_client.get_thermostat.reset_mock()

    freezer.tick(FAST_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_gkp_client.get_thermostat.assert_not_called()


@pytest.mark.parametrize(
    ("service", "data", "client_method"),
    [
        pytest.param(
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 23.5},
            "set_temperature",
            id="set_temperature",
        ),
        pytest.param(
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: PRESET_ECO},
            "set_mode",
            id="set_mode",
        ),
    ],
)
async def test_command_rate_limited(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    data: dict[str, Any],
    client_method: str,
) -> None:
    """Test commands tell the user when to try again when rate limited."""
    await setup_integration(hass, mock_config_entry)
    getattr(mock_gkp_client, client_method).side_effect = GkpRateLimitError(
        "limited", 30
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID, **data},
            blocking=True,
        )

    assert err.value.translation_key == "rate_limited"
    assert err.value.translation_placeholders == {"retry_after": "30"}


@pytest.mark.parametrize(
    ("duration", "expected_minutes"),
    [
        pytest.param(timedelta(minutes=90), 90, id="whole_minutes"),
        pytest.param(timedelta(minutes=3, seconds=30), 4, id="rounded_up"),
    ],
)
async def test_activate_boost(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    duration: timedelta,
    expected_minutes: int,
) -> None:
    """Test activating boost with a temperature and a duration."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ACTIVATE_BOOST,
        {
            ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID,
            ATTR_TEMPERATURE: 24.5,
            ATTR_DURATION: duration,
        },
        blocking=True,
    )

    mock_gkp_client.activate_boost.assert_called_once_with(
        LIVING_ROOM_ID, 24.5, expected_minutes
    )


@pytest.mark.parametrize("temperature", [4.5, 35.5])
async def test_activate_boost_temperature_out_of_range(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    temperature: float,
) -> None:
    """Test boost temperatures outside the allowed range are rejected."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_BOOST,
            {
                ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID,
                ATTR_TEMPERATURE: temperature,
                ATTR_DURATION: timedelta(minutes=90),
            },
            blocking=True,
        )

    assert err.value.translation_key == "boost_temperature_out_of_range"
    mock_gkp_client.activate_boost.assert_not_called()


@pytest.mark.parametrize(
    "duration", [timedelta(minutes=2), timedelta(days=1, minutes=1)]
)
async def test_activate_boost_duration_out_of_range(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    duration: timedelta,
) -> None:
    """Test boost durations outside the firmware range are rejected."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_BOOST,
            {
                ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID,
                ATTR_TEMPERATURE: 24.5,
                ATTR_DURATION: duration,
            },
            blocking=True,
        )

    mock_gkp_client.activate_boost.assert_not_called()


@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        pytest.param(GkpConnectionError("lost"), "activate_boost_error", id="error"),
        pytest.param(
            GkpRateLimitError("limited", 30), "rate_limited", id="rate_limited"
        ),
    ],
)
async def test_activate_boost_error(
    hass: HomeAssistant,
    mock_gkp_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    translation_key: str,
) -> None:
    """Test API errors while activating boost."""
    await setup_integration(hass, mock_config_entry)
    mock_gkp_client.activate_boost.side_effect = error

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_BOOST,
            {
                ATTR_ENTITY_ID: LIVING_ROOM_ENTITY_ID,
                ATTR_TEMPERATURE: 24.5,
                ATTR_DURATION: timedelta(minutes=90),
            },
            blocking=True,
        )

    assert err.value.translation_key == translation_key
