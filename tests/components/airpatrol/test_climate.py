"""Test the AirPatrol climate platform."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from airpatrol.api import AirPatrolAPI
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.airpatrol.climate import (
    HA_TO_AP_FAN_MODES,
    HA_TO_AP_HVAC_MODES,
    HA_TO_AP_SWING_MODES,
)
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_HIGH,
    FAN_LOW,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_OFF,
    SWING_ON,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    SnapshotAssertion,
    async_fire_time_changed,
    snapshot_platform,
)


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override the platforms to load for airpatrol."""
    with patch(
        "homeassistant.components.airpatrol.PLATFORMS",
        [Platform.CLIMATE],
    ):
        yield


@pytest.mark.parametrize(
    "climate_data",
    [
        {
            "ParametersData": {
                "PumpPower": "on",
                "PumpTemp": "22.000",
                "PumpMode": "cool",
                "FanSpeed": "max",
                "Swing": "off",
            },
            "RoomTemp": "22.5",
            "RoomHumidity": "45",
        },
        None,
    ],
)
async def test_climate_entities(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        load_integration.entry_id,
    )


async def test_climate_entity_unavailable(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
    get_data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test climate entity when climate data is missing."""
    state = hass.states.get("climate.living_room")
    assert state
    assert state.state == HVACMode.COOL

    get_data[0]["climate"] = None
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room")
    assert state
    assert state.state == "unavailable"


async def test_climate_set_temperature(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
    climate_data: dict[str, Any],
) -> None:
    """Test setting temperature."""
    TARGET_TEMP = 25.0

    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_TEMPERATURE] == 22.0

    climate_data["ParametersData"]["PumpTemp"] = f"{TARGET_TEMP:.3f}"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            CONF_ENTITY_ID: state.entity_id,
            ATTR_TEMPERATURE: TARGET_TEMP,
        },
    )

    get_client.set_unit_climate_data.assert_called_once()
    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_TEMPERATURE] == TARGET_TEMP


async def test_climate_set_hvac_mode(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
    climate_data: dict[str, Any],
) -> None:
    """Test setting HVAC mode."""
    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.COOL

    climate_data["ParametersData"]["PumpMode"] = HA_TO_AP_HVAC_MODES[HVACMode.HEAT]
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            CONF_ENTITY_ID: state.entity_id,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
    )

    get_client.set_unit_climate_data.assert_called_once()
    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.HEAT


async def test_climate_set_fan_mode(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
    climate_data: dict[str, Any],
) -> None:
    """Test setting fan mode."""
    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_FAN_MODE] == FAN_HIGH

    climate_data["ParametersData"]["FanSpeed"] = HA_TO_AP_FAN_MODES[FAN_LOW]
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            CONF_ENTITY_ID: state.entity_id,
            ATTR_FAN_MODE: FAN_LOW,
        },
    )

    get_client.set_unit_climate_data.assert_called_once()
    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_FAN_MODE] == FAN_LOW


async def test_climate_set_swing_mode(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
    climate_data: dict[str, Any],
) -> None:
    """Test setting swing mode."""
    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_SWING_MODE] == SWING_OFF

    climate_data["ParametersData"]["Swing"] = HA_TO_AP_SWING_MODES[SWING_ON]
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {
            CONF_ENTITY_ID: state.entity_id,
            ATTR_SWING_MODE: SWING_ON,
        },
    )

    get_client.set_unit_climate_data.assert_called_once()
    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_SWING_MODE] == SWING_ON


@pytest.mark.parametrize(
    "climate_data",
    [
        {
            "ParametersData": {
                "PumpPower": "off",
                "PumpTemp": "22.000",
                "PumpMode": "cool",
                "FanSpeed": "max",
                "Swing": "off",
            },
            "RoomTemp": "22.5",
            "RoomHumidity": "45",
        }
    ],
)
async def test_climate_turn_on(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
    climate_data: dict[str, Any],
) -> None:
    """Test turning climate on."""
    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.OFF

    climate_data["ParametersData"]["PumpPower"] = "on"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {
            CONF_ENTITY_ID: state.entity_id,
        },
    )

    get_client.set_unit_climate_data.assert_called_once()
    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.COOL


async def test_climate_turn_off(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
    climate_data: dict[str, Any],
) -> None:
    """Test turning climate off."""
    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.COOL

    climate_data["ParametersData"]["PumpPower"] = "off"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {
            CONF_ENTITY_ID: state.entity_id,
        },
    )

    get_client.set_unit_climate_data.assert_called_once()
    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.OFF


@pytest.mark.parametrize(
    "climate_data",
    [
        {
            "ParametersData": {
                "PumpPower": "on",
                "PumpTemp": "22.000",
                "PumpMode": "heat",
                "FanSpeed": "max",
                "Swing": "off",
            },
            "RoomTemp": "22.5",
            "RoomHumidity": "45",
        }
    ],
)
async def test_climate_heat_mode(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
) -> None:
    """Test climate in heat mode."""
    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.HEAT


async def test_climate_set_temperature_api_error(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
) -> None:
    """Test async_set_temperature handles API error."""
    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_TEMPERATURE] == 22.0

    get_client.set_unit_climate_data.side_effect = Exception("API Error")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            CONF_ENTITY_ID: state.entity_id,
            ATTR_TEMPERATURE: 25.0,
        },
    )

    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_TEMPERATURE] == 22.0


@pytest.mark.parametrize(
    "climate_data",
    [
        {
            "ParametersData": {
                "PumpPower": "off",
                "PumpTemp": "22.000",
                "PumpMode": "cool",
                "FanSpeed": "sideways",
                "Swing": "off",
            },
            "RoomTemp": "22.5",
            "RoomHumidity": "45",
        }
    ],
)
async def test_climate_fan_mode_invalid(
    hass: HomeAssistant,
    get_client: AirPatrolAPI,
    get_data: dict[str, Any],
    load_integration: MockConfigEntry,
) -> None:
    """Test fan_mode with unexpected value."""
    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_FAN_MODE] is None


@pytest.mark.parametrize(
    "climate_data",
    [
        {
            "ParametersData": {
                "PumpPower": "off",
                "PumpTemp": "22.000",
                "PumpMode": "cool",
                "FanSpeed": "max",
                "Swing": "sideways",
            },
            "RoomTemp": "22.5",
            "RoomHumidity": "45",
        }
    ],
)
async def test_climate_swing_mode_invalid(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
) -> None:
    """Test swing_mode with unexpected value."""
    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_SWING_MODE] is None
