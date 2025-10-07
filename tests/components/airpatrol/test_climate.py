"""Test the AirPatrol climate platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.airpatrol.climate import (
    HA_TO_AP_FAN_MODES,
    HA_TO_AP_HVAC_MODES,
    HA_TO_AP_SWING_MODES,
)
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import SnapshotAssertion, async_fire_time_changed, snapshot_platform


async def test_async_setup_entry_adds_entities(
    hass: HomeAssistant,
    load_integration,
    mock_airpatrol_client,
    entity_registry: er.EntityRegistry,
    get_data,
    snapshot: SnapshotAssertion,
    mock_config_entry,
) -> None:
    """Test async_setup_entry creates and adds AirPatrolClimate entities that have climate data."""
    unit_with_climate = get_data(unit_id="unit1", name="Unit 1")
    unit_without_climate = get_data(unit_id="unit2", name="Unit 2", climate=None)
    mock_airpatrol_client.get_data.return_value = [
        unit_with_climate[0],
        unit_without_climate[0],
    ]
    await load_integration()

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


async def test_climate_entity_initialization(
    hass: HomeAssistant, load_integration, mock_airpatrol_client, get_data
) -> None:
    """Test climate entity initialization."""
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state
    assert state.state == "cool"


async def test_climate_entity_unavailable(
    hass: HomeAssistant,
    load_integration,
    mock_airpatrol_client,
    get_data,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test climate entity when climate data is missing."""
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state

    mock_airpatrol_client.get_data.return_value = get_data(climate=None)
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room")
    assert state
    assert state.state == "unavailable"


async def test_climate_hvac_modes(
    hass: HomeAssistant, load_integration, mock_airpatrol_client
) -> None:
    """Test climate HVAC modes."""
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.OFF,
    ]


async def test_climate_fan_modes(
    hass: HomeAssistant, load_integration, mock_airpatrol_client
) -> None:
    """Test climate fan modes."""
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state
    assert state.attributes[ATTR_FAN_MODES] == [FAN_LOW, FAN_HIGH, FAN_AUTO]


async def test_climate_swing_modes(
    hass: HomeAssistant, load_integration, mock_airpatrol_client
) -> None:
    """Test climate swing modes."""
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state
    assert state.attributes[ATTR_SWING_MODES] == [SWING_ON, SWING_OFF]


async def test_climate_temperature_range(
    hass: HomeAssistant, load_integration, mock_airpatrol_client
) -> None:
    """Test climate temperature range."""
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state
    assert state.attributes[ATTR_MIN_TEMP] == 16.0
    assert state.attributes[ATTR_MAX_TEMP] == 30.0


async def test_climate_set_temperature(
    hass: HomeAssistant,
    load_integration,
    mock_airpatrol_client,
    get_data,
) -> None:
    """Test setting temperature."""
    await load_integration()

    TARGET_TEMP = 25.0

    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_TEMPERATURE] == 22.0

    mock_airpatrol_client.get_data.return_value = get_data(target_temp=TARGET_TEMP)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            CONF_ENTITY_ID: state.entity_id,
            ATTR_TEMPERATURE: TARGET_TEMP,
        },
    )

    mock_airpatrol_client.set_unit_climate_data.assert_called_once()
    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_TEMPERATURE] == TARGET_TEMP


async def test_climate_set_hvac_mode(
    hass: HomeAssistant,
    load_integration,
    mock_airpatrol_client,
    get_data,
) -> None:
    """Test setting HVAC mode."""
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.COOL

    mock_airpatrol_client.get_data.return_value = get_data(
        mode=HA_TO_AP_HVAC_MODES[HVACMode.HEAT]
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            CONF_ENTITY_ID: state.entity_id,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
    )

    mock_airpatrol_client.set_unit_climate_data.assert_called_once()
    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.HEAT


async def test_climate_set_fan_mode(
    hass: HomeAssistant,
    load_integration,
    mock_airpatrol_client,
    get_data,
) -> None:
    """Test setting fan mode."""
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_FAN_MODE] == FAN_HIGH

    mock_airpatrol_client.get_data.return_value = get_data(
        fan_speed=HA_TO_AP_FAN_MODES[FAN_LOW]
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            CONF_ENTITY_ID: state.entity_id,
            ATTR_FAN_MODE: FAN_LOW,
        },
    )

    mock_airpatrol_client.set_unit_climate_data.assert_called_once()
    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_FAN_MODE] == FAN_LOW


async def test_climate_set_swing_mode(
    hass: HomeAssistant,
    load_integration,
    mock_airpatrol_client,
    get_data,
) -> None:
    """Test setting swing mode."""
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_SWING_MODE] == SWING_OFF

    mock_airpatrol_client.get_data.return_value = get_data(
        swing=HA_TO_AP_SWING_MODES[SWING_ON]
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {
            CONF_ENTITY_ID: state.entity_id,
            ATTR_SWING_MODE: SWING_ON,
        },
    )

    mock_airpatrol_client.set_unit_climate_data.assert_called_once()
    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_SWING_MODE] == SWING_ON


async def test_climate_turn_on(
    hass: HomeAssistant,
    load_integration,
    mock_airpatrol_client,
    get_data,
) -> None:
    """Test turning climate on."""
    mock_airpatrol_client.get_data.return_value = get_data(power="off")
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.OFF

    expected_data = get_data(power="on")

    mock_airpatrol_client.get_data.return_value = expected_data

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {
            CONF_ENTITY_ID: state.entity_id,
        },
    )

    mock_airpatrol_client.set_unit_climate_data.assert_called_once_with(
        expected_data[0]["unit_id"], expected_data[0]["climate"]
    )
    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.COOL


async def test_climate_turn_off(
    hass: HomeAssistant,
    load_integration,
    mock_airpatrol_client,
    get_data,
) -> None:
    """Test turning climate off."""
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.COOL

    # Mock the API call to return expected response data
    expected_data = get_data(power="off")
    mock_airpatrol_client.get_data.return_value = expected_data

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {
            CONF_ENTITY_ID: state.entity_id,
        },
    )

    mock_airpatrol_client.set_unit_climate_data.assert_called_once_with(
        expected_data[0]["unit_id"], expected_data[0]["climate"]
    )

    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.OFF


async def test_climate_heat_mode(
    hass: HomeAssistant,
    load_integration,
    mock_airpatrol_client,
    get_data,
) -> None:
    """Test climate in heat mode."""
    mock_airpatrol_client.get_data.return_value = get_data(mode="heat", power="on")
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state.state == HVACMode.HEAT


async def test_climate_set_temperature_api_error(
    hass: HomeAssistant,
    load_integration,
    mock_airpatrol_client,
) -> None:
    """Test async_set_temperature handles API error."""
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_TEMPERATURE] == 22.0

    mock_airpatrol_client.set_unit_climate_data.side_effect = Exception("API Error")

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


async def test_climate_fan_mode_invalid(
    hass: HomeAssistant,
    mock_airpatrol_client,
    get_data,
    load_integration,
) -> None:
    """Test fan_mode with unexpected value."""
    mock_airpatrol_client.get_data.return_value = get_data(fan_speed="sideways")
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_FAN_MODE] is None


async def test_climate_swing_mode_invalid(
    hass: HomeAssistant,
    get_data,
    load_integration,
    mock_airpatrol_client,
) -> None:
    """Test swing_mode with unexpected value."""
    mock_airpatrol_client.get_data.return_value = get_data(swing="sideways")
    await load_integration()

    state = hass.states.get("climate.living_room")
    assert state.attributes[ATTR_SWING_MODE] is None
