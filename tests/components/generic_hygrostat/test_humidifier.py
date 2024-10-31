"""The tests for the generic_hygrostat."""

import datetime

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant.components import input_boolean, switch
from homeassistant.components.generic_hygrostat import (
    DOMAIN as GENERIC_HYDROSTAT_DOMAIN,
)
from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    MODE_AWAY,
    MODE_NORMAL,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
import homeassistant.core as ha
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    CoreState,
    HomeAssistant,
    ServiceCall,
    State,
    callback,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import StateType
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    async_fire_time_changed,
    mock_restore_cache,
    setup_test_component_platform,
)
from tests.components.switch.common import MockSwitch

ENTITY = "humidifier.test"
ENT_SENSOR = "sensor.test"
ENT_SWITCH = "switch.test"
ATTR_SAVED_HUMIDITY = "saved_humidity"
MIN_HUMIDITY = 20
MAX_HUMIDITY = 65
TARGET_HUMIDITY = 42


async def test_setup_missing_conf(hass: HomeAssistant) -> None:
    """Test set up humidity_control with missing config values."""
    config = {
        "platform": "generic_hygrostat",
        "name": "test",
        "target_sensor": ENT_SENSOR,
    }
    with assert_setup_component(0):
        await async_setup_component(hass, "humidifier", {"humidifier": config})
        await hass.async_block_till_done()


async def test_valid_conf(hass: HomeAssistant) -> None:
    """Test set up generic_hygrostat with valid config values."""
    assert await async_setup_component(
        hass,
        "humidifier",
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
async def setup_comp_1(hass: HomeAssistant) -> None:
    """Initialize components."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_comp_1")
async def test_humidifier_input_boolean(hass: HomeAssistant) -> None:
    """Test humidifier switching input_boolean."""
    humidifier_switch = "input_boolean.test"
    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test": None}}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "humidifier": humidifier_switch,
                "target_sensor": ENT_SENSOR,
                "initial_state": True,
            }
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get(humidifier_switch).state == STATE_OFF

    _setup_sensor(hass, 23)
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 32},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(humidifier_switch).state == STATE_ON
    assert hass.states.get(ENTITY).attributes.get("action") == "humidifying"


@pytest.mark.usefixtures("setup_comp_1")
async def test_humidifier_switch(
    hass: HomeAssistant, mock_switch_entities: list[MockSwitch]
) -> None:
    """Test humidifier switching test switch."""
    setup_test_component_platform(hass, switch.DOMAIN, mock_switch_entities)
    switch_1 = mock_switch_entities[1]
    assert await async_setup_component(
        hass, switch.DOMAIN, {"switch": {"platform": "test"}}
    )
    await hass.async_block_till_done()
    humidifier_switch = switch_1.entity_id

    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "humidifier": humidifier_switch,
                "target_sensor": ENT_SENSOR,
                "initial_state": True,
            }
        },
    )

    await hass.async_block_till_done()
    assert hass.states.get(humidifier_switch).state == STATE_OFF

    _setup_sensor(hass, 23)
    await hass.async_block_till_done()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 32},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(humidifier_switch).state == STATE_ON
    assert hass.states.get(ENTITY).attributes.get("action") == "humidifying"


@pytest.mark.usefixtures("setup_comp_1")
async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test setting a unique ID."""
    unique_id = "some_unique_id"
    _setup_sensor(hass, 18)
    await _setup_switch(hass, True)
    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "unique_id": unique_id,
            }
        },
    )
    await hass.async_block_till_done()

    entry = entity_registry.async_get(ENTITY)
    assert entry
    assert entry.unique_id == unique_id


def _setup_sensor(hass: HomeAssistant, humidity: StateType) -> None:
    """Set up the test sensor."""
    hass.states.async_set(ENT_SENSOR, humidity)


@pytest.fixture
async def setup_comp_0(hass: HomeAssistant) -> None:
    """Initialize components."""
    _setup_sensor(hass, 45)
    hass.states.async_set(ENT_SWITCH, STATE_OFF)
    await hass.async_block_till_done()
    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 2,
                "wet_tolerance": 4,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "device_class": "dehumidifier",
                "away_humidity": 35,
                "initial_state": True,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
async def setup_comp_2(hass: HomeAssistant) -> None:
    """Initialize components."""
    _setup_sensor(hass, 45)
    hass.states.async_set(ENT_SWITCH, STATE_OFF)
    await hass.async_block_till_done()
    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 2,
                "wet_tolerance": 4,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "away_humidity": 35,
                "initial_state": True,
            }
        },
    )
    await hass.async_block_till_done()


async def test_unavailable_state(hass: HomeAssistant) -> None:
    """Test the setting of defaults to unknown."""
    await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 2,
                "wet_tolerance": 4,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "away_humidity": 35,
            }
        },
    )
    # The target sensor is unavailable, that should propagate to the humidifier entity:
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE

    # Sensor online
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_OFF


async def test_setup_defaults_to_unknown(hass: HomeAssistant) -> None:
    """Test the setting of defaults to unknown."""
    await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 2,
                "wet_tolerance": 4,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "away_humidity": 35,
            }
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("setup_comp_2")
async def test_default_setup_params(hass: HomeAssistant) -> None:
    """Test the setup with default parameters."""
    state = hass.states.get(ENTITY)
    assert state.attributes.get("min_humidity") == 0
    assert state.attributes.get("max_humidity") == 100
    assert state.attributes.get("humidity") == 0
    assert state.attributes.get("action") == "idle"


@pytest.mark.usefixtures("setup_comp_0")
async def test_default_setup_params_dehumidifier(hass: HomeAssistant) -> None:
    """Test the setup with default parameters for dehumidifier."""
    state = hass.states.get(ENTITY)
    assert state.attributes.get("min_humidity") == 0
    assert state.attributes.get("max_humidity") == 100
    assert state.attributes.get("humidity") == 100
    assert state.attributes.get("action") == "idle"


@pytest.mark.usefixtures("setup_comp_2")
async def test_get_modes(hass: HomeAssistant) -> None:
    """Test that the attributes returns the correct modes."""
    state = hass.states.get(ENTITY)
    modes = state.attributes.get("available_modes")
    assert modes == [MODE_NORMAL, MODE_AWAY]


@pytest.mark.usefixtures("setup_comp_2")
async def test_set_target_humidity(hass: HomeAssistant) -> None:
    """Test the setting of the target humidity."""
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 40},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("humidity") == 40
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: None},
            blocking=True,
        )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("humidity") == 40


@pytest.mark.usefixtures("setup_comp_2")
async def test_set_away_mode(hass: HomeAssistant) -> None:
    """Test the setting away mode."""
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 44},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: ENTITY, ATTR_MODE: MODE_AWAY},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("humidity") == 35


@pytest.mark.usefixtures("setup_comp_2")
async def test_set_away_mode_and_restore_prev_humidity(hass: HomeAssistant) -> None:
    """Test the setting and removing away mode.

    Verify original humidity is restored.
    """
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 44},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: ENTITY, ATTR_MODE: MODE_AWAY},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("humidity") == 35
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: ENTITY, ATTR_MODE: MODE_NORMAL},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("humidity") == 44


@pytest.mark.usefixtures("setup_comp_2")
async def test_set_away_mode_twice_and_restore_prev_humidity(
    hass: HomeAssistant,
) -> None:
    """Test the setting away mode twice in a row.

    Verify original humidity is restored.
    """
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 44},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: ENTITY, ATTR_MODE: MODE_AWAY},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: ENTITY, ATTR_MODE: MODE_AWAY},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("humidity") == 35
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: ENTITY, ATTR_MODE: MODE_NORMAL},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("humidity") == 44


@pytest.mark.usefixtures("setup_comp_2")
async def test_sensor_affects_attribute(hass: HomeAssistant) -> None:
    """Test that the sensor changes are reflected in the current_humidity attribute."""
    state = hass.states.get(ENTITY)
    assert state.attributes.get("current_humidity") == 45

    _setup_sensor(hass, 47)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY)
    assert state.attributes.get("current_humidity") == 47


@pytest.mark.usefixtures("setup_comp_2")
async def test_sensor_bad_value(hass: HomeAssistant) -> None:
    """Test sensor that have None as state."""
    assert hass.states.get(ENTITY).state == STATE_ON

    _setup_sensor(hass, None)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("setup_comp_2")
async def test_sensor_bad_value_twice(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test sensor that the second bad value is not logged as warning."""
    assert hass.states.get(ENTITY).state == STATE_ON

    _setup_sensor(hass, "forty")
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    assert [
        rec.levelname
        for rec in caplog.records
        if "Unable to update from sensor" in rec.message
    ] == ["WARNING"]

    caplog.clear()

    _setup_sensor(hass, "fifty")
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    assert [
        rec.levelname
        for rec in caplog.records
        if "Unable to update from sensor" in rec.message
    ] == ["DEBUG"]


@pytest.mark.usefixtures("setup_comp_2")
async def test_set_target_humidity_humidifier_on(hass: HomeAssistant) -> None:
    """Test if target humidity turn humidifier on."""
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 36)
    await hass.async_block_till_done()
    calls.clear()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 45},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_2")
async def test_set_target_humidity_humidifier_off(hass: HomeAssistant) -> None:
    """Test if target humidity turn humidifier off."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    calls.clear()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 36},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_2")
async def test_humidity_change_humidifier_on_within_tolerance(
    hass: HomeAssistant,
) -> None:
    """Test if humidity change doesn't turn on within tolerance."""
    calls = await _setup_switch(hass, False)
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 44},
        blocking=True,
    )
    await hass.async_block_till_done()
    _setup_sensor(hass, 43)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("setup_comp_2")
async def test_humidity_change_humidifier_on_outside_tolerance(
    hass: HomeAssistant,
) -> None:
    """Test if humidity change turn humidifier on outside dry tolerance."""
    calls = await _setup_switch(hass, False)
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 44},
        blocking=True,
    )
    await hass.async_block_till_done()
    _setup_sensor(hass, 42)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_2")
async def test_humidity_change_humidifier_off_within_tolerance(
    hass: HomeAssistant,
) -> None:
    """Test if humidity change doesn't turn off within tolerance."""
    calls = await _setup_switch(hass, True)
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 46},
        blocking=True,
    )
    await hass.async_block_till_done()
    _setup_sensor(hass, 48)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("setup_comp_2")
async def test_humidity_change_humidifier_off_outside_tolerance(
    hass: HomeAssistant,
) -> None:
    """Test if humidity change turn humidifier off outside wet tolerance."""
    calls = await _setup_switch(hass, True)
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 46},
        blocking=True,
    )
    await hass.async_block_till_done()
    _setup_sensor(hass, 50)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_2")
async def test_operation_mode_humidify(hass: HomeAssistant) -> None:
    """Test change mode from OFF to HUMIDIFY.

    Switch turns on when humidity below setpoint and mode changes.
    """
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 45},
        blocking=True,
    )
    await hass.async_block_till_done()
    _setup_sensor(hass, 40)
    await hass.async_block_till_done()
    calls = await _setup_switch(hass, False)
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


async def _setup_switch(hass: HomeAssistant, is_on: bool) -> list[ServiceCall]:
    """Set up the test switch."""
    hass.states.async_set(ENT_SWITCH, STATE_ON if is_on else STATE_OFF)
    calls = []

    @callback
    def log_call(call: ServiceCall) -> None:
        """Log service calls."""
        calls.append(call)

    hass.services.async_register(ha.DOMAIN, SERVICE_TURN_ON, log_call)
    hass.services.async_register(ha.DOMAIN, SERVICE_TURN_OFF, log_call)

    await hass.async_block_till_done()
    return calls


@pytest.fixture
async def setup_comp_3(hass: HomeAssistant) -> None:
    """Initialize components."""
    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 2,
                "wet_tolerance": 4,
                "away_humidity": 30,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "device_class": "dehumidifier",
                "initial_state": True,
                "target_humidity": 40,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_comp_3")
async def test_set_target_humidity_dry_off(hass: HomeAssistant) -> None:
    """Test if target humidity turn dry off."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 50)
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 55},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH
    assert hass.states.get(ENTITY).attributes.get("action") == "drying"


@pytest.mark.usefixtures("setup_comp_3")
async def test_turn_away_mode_on_drying(hass: HomeAssistant) -> None:
    """Test the setting away mode when drying."""
    await _setup_switch(hass, True)
    _setup_sensor(hass, 50)
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 34},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: ENTITY, ATTR_MODE: MODE_AWAY},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("humidity") == 30


@pytest.mark.usefixtures("setup_comp_3")
async def test_operation_mode_dry(hass: HomeAssistant) -> None:
    """Test change mode from OFF to DRY.

    Switch turns on when humidity below setpoint and state changes.
    """
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert len(calls) == 0
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_3")
async def test_set_target_humidity_dry_on(hass: HomeAssistant) -> None:
    """Test if target humidity turn dry on."""
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_3")
async def test_init_ignores_tolerance(hass: HomeAssistant) -> None:
    """Test if tolerance is ignored on initialization."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 39)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_3")
async def test_humidity_change_dry_off_within_tolerance(hass: HomeAssistant) -> None:
    """Test if humidity change doesn't turn dry off within tolerance."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 45)
    _setup_sensor(hass, 39)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("setup_comp_3")
async def test_set_humidity_change_dry_off_outside_tolerance(
    hass: HomeAssistant,
) -> None:
    """Test if humidity change turn dry off."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 36)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_3")
async def test_humidity_change_dry_on_within_tolerance(hass: HomeAssistant) -> None:
    """Test if humidity change doesn't turn dry on within tolerance."""
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 37)
    _setup_sensor(hass, 41)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("setup_comp_3")
async def test_humidity_change_dry_on_outside_tolerance(hass: HomeAssistant) -> None:
    """Test if humidity change turn dry on."""
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_3")
async def test_running_when_operating_mode_is_off_2(hass: HomeAssistant) -> None:
    """Test that the switch turns off when enabled is set False."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH
    assert hass.states.get(ENTITY).attributes.get("action") == "off"


@pytest.mark.usefixtures("setup_comp_3")
async def test_no_state_change_when_operation_mode_off_2(hass: HomeAssistant) -> None:
    """Test that the switch doesn't turn on when enabled is False."""
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0
    assert hass.states.get(ENTITY).attributes.get("action") == "off"


@pytest.fixture
async def setup_comp_4(hass: HomeAssistant) -> None:
    """Initialize components."""
    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 3,
                "wet_tolerance": 3,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "device_class": "dehumidifier",
                "min_cycle_duration": {"minutes": 10},
                "initial_state": True,
                "target_humidity": 40,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_comp_4")
async def test_humidity_change_dry_trigger_on_not_long_enough(
    hass: HomeAssistant,
) -> None:
    """Test if humidity change turn dry on."""
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 0

    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("setup_comp_4")
async def test_humidity_change_dry_trigger_on_long_enough(hass: HomeAssistant) -> None:
    """Test if humidity change turn dry on."""
    fake_changed = datetime.datetime(1970, 11, 11, 11, 11, 11, tzinfo=datetime.UTC)
    with freeze_time(fake_changed):
        calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 0

    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_4")
async def test_humidity_change_dry_trigger_off_not_long_enough(
    hass: HomeAssistant,
) -> None:
    """Test if humidity change turn dry on."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0

    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("setup_comp_4")
async def test_humidity_change_dry_trigger_off_long_enough(hass: HomeAssistant) -> None:
    """Test if humidity change turn dry on."""
    fake_changed = datetime.datetime(1970, 11, 11, 11, 11, 11, tzinfo=datetime.UTC)
    with freeze_time(fake_changed):
        calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0

    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_4")
async def test_mode_change_dry_trigger_off_not_long_enough(hass: HomeAssistant) -> None:
    """Test if mode change turns dry off despite minimum cycle."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "homeassistant"
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_4")
async def test_mode_change_dry_trigger_on_not_long_enough(hass: HomeAssistant) -> None:
    """Test if mode change turns dry on despite minimum cycle."""
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "homeassistant"
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.fixture
async def setup_comp_6(hass: HomeAssistant) -> None:
    """Initialize components."""
    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 3,
                "wet_tolerance": 3,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "min_cycle_duration": {"minutes": 10},
                "initial_state": True,
                "target_humidity": 40,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_comp_6")
async def test_humidity_change_humidifier_trigger_off_not_long_enough(
    hass: HomeAssistant,
) -> None:
    """Test if humidity change doesn't turn humidifier off because of time."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 0

    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("setup_comp_6")
async def test_humidity_change_humidifier_trigger_on_not_long_enough(
    hass: HomeAssistant,
) -> None:
    """Test if humidity change doesn't turn humidifier on because of time."""
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0

    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.usefixtures("setup_comp_6")
async def test_humidity_change_humidifier_trigger_on_long_enough(
    hass: HomeAssistant,
) -> None:
    """Test if humidity change turn humidifier on after min cycle."""
    fake_changed = datetime.datetime(1970, 11, 11, 11, 11, 11, tzinfo=datetime.UTC)
    with freeze_time(fake_changed):
        calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0

    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_6")
async def test_humidity_change_humidifier_trigger_off_long_enough(
    hass: HomeAssistant,
) -> None:
    """Test if humidity change turn humidifier off after min cycle."""
    fake_changed = datetime.datetime(1970, 11, 11, 11, 11, 11, tzinfo=datetime.UTC)
    with freeze_time(fake_changed):
        calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 0

    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_6")
async def test_mode_change_humidifier_trigger_off_not_long_enough(
    hass: HomeAssistant,
) -> None:
    """Test if mode change turns humidifier off despite minimum cycle."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 0

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "homeassistant"
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_6")
async def test_mode_change_humidifier_trigger_on_not_long_enough(
    hass: HomeAssistant,
) -> None:
    """Test if mode change turns humidifier on despite minimum cycle."""
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 0

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "homeassistant"
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.fixture
async def setup_comp_7(hass: HomeAssistant) -> None:
    """Initialize components."""
    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 3,
                "wet_tolerance": 3,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "device_class": "dehumidifier",
                "min_cycle_duration": {"minutes": 15},
                "keep_alive": {"minutes": 10},
                "initial_state": True,
                "target_humidity": 40,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_comp_7")
async def test_humidity_change_dry_trigger_on_long_enough_3(
    hass: HomeAssistant,
) -> None:
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_7")
async def test_humidity_change_dry_trigger_off_long_enough_3(
    hass: HomeAssistant,
) -> None:
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.fixture
async def setup_comp_8(hass: HomeAssistant) -> None:
    """Initialize components."""
    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 3,
                "wet_tolerance": 3,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "min_cycle_duration": {"minutes": 15},
                "keep_alive": {"minutes": 10},
                "initial_state": True,
                "target_humidity": 40,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_comp_8")
async def test_humidity_change_humidifier_trigger_on_long_enough_2(
    hass: HomeAssistant,
) -> None:
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


@pytest.mark.usefixtures("setup_comp_8")
async def test_humidity_change_humidifier_trigger_off_long_enough_2(
    hass: HomeAssistant,
) -> None:
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


async def test_float_tolerance_values(hass: HomeAssistant) -> None:
    """Test if dehumidifier does not turn on within floating point tolerance."""
    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 0.2,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "device_class": "dehumidifier",
                "initial_state": True,
                "target_humidity": 40,
            }
        },
    )
    await hass.async_block_till_done()
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 45)
    _setup_sensor(hass, 39.9)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_float_tolerance_values_2(hass: HomeAssistant) -> None:
    """Test if dehumidifier turns off when oudside of floating point tolerance values."""
    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 0.2,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "device_class": "dehumidifier",
                "initial_state": True,
                "target_humidity": 40,
            }
        },
    )
    await hass.async_block_till_done()
    calls = await _setup_switch(hass, True)
    _setup_sensor(hass, 39.7)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HOMEASSISTANT_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


async def test_custom_setup_params(hass: HomeAssistant) -> None:
    """Test the setup with custom parameters."""
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    result = await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "min_humidity": MIN_HUMIDITY,
                "max_humidity": MAX_HUMIDITY,
                "target_humidity": TARGET_HUMIDITY,
            }
        },
    )
    await hass.async_block_till_done()
    assert result
    state = hass.states.get(ENTITY)
    assert state.attributes.get("min_humidity") == MIN_HUMIDITY
    assert state.attributes.get("max_humidity") == MAX_HUMIDITY
    assert state.attributes.get("humidity") == TARGET_HUMIDITY


async def test_restore_state(hass: HomeAssistant) -> None:
    """Ensure states are restored on startup."""
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    mock_restore_cache(
        hass,
        (
            State(
                "humidifier.test_hygrostat",
                STATE_OFF,
                {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: "40", ATTR_MODE: MODE_AWAY},
            ),
        ),
    )

    hass.set_state(CoreState.starting)

    await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test_hygrostat",
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "away_humidity": 32,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("humidifier.test_hygrostat")
    assert state.attributes[ATTR_HUMIDITY] == 40
    assert state.attributes[ATTR_MODE] == MODE_AWAY
    assert state.state == STATE_OFF


async def test_restore_state_target_humidity(hass: HomeAssistant) -> None:
    """Ensure restore target humidity if available."""
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    mock_restore_cache(
        hass,
        (
            State(
                "humidifier.test_hygrostat",
                STATE_OFF,
                {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: "40"},
            ),
        ),
    )

    hass.set_state(CoreState.starting)

    await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test_hygrostat",
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "away_humidity": 32,
                "target_humidity": 50,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("humidifier.test_hygrostat")
    assert state.attributes[ATTR_HUMIDITY] == 40
    assert state.state == STATE_OFF


async def test_restore_state_and_return_to_normal(hass: HomeAssistant) -> None:
    """Ensure retain of target humidity for normal mode."""
    _setup_sensor(hass, 55)
    await hass.async_block_till_done()
    mock_restore_cache(
        hass,
        (
            State(
                "humidifier.test_hygrostat",
                STATE_OFF,
                {
                    ATTR_ENTITY_ID: ENTITY,
                    ATTR_HUMIDITY: "40",
                    ATTR_MODE: MODE_AWAY,
                    ATTR_SAVED_HUMIDITY: "50",
                },
            ),
        ),
    )

    hass.set_state(CoreState.starting)

    await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test_hygrostat",
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "away_humidity": 32,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("humidifier.test_hygrostat")
    assert state.attributes[ATTR_HUMIDITY] == 40
    assert state.attributes[ATTR_SAVED_HUMIDITY] == 50
    assert state.attributes[ATTR_MODE] == MODE_AWAY
    assert state.state == STATE_OFF

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: "humidifier.test_hygrostat", ATTR_MODE: MODE_NORMAL},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("humidifier.test_hygrostat")
    assert state.attributes[ATTR_HUMIDITY] == 50
    assert state.attributes[ATTR_MODE] == MODE_NORMAL
    assert state.state == STATE_OFF


async def test_no_restore_state(hass: HomeAssistant) -> None:
    """Ensure states are restored on startup if they exist.

    Allows for graceful reboot.
    """
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    mock_restore_cache(
        hass,
        (
            State(
                "humidifier.test_hygrostat",
                STATE_OFF,
                {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: "40", ATTR_MODE: MODE_AWAY},
            ),
        ),
    )

    hass.set_state(CoreState.starting)

    await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test_hygrostat",
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "target_humidity": 42,
                "away_humidity": 35,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("humidifier.test_hygrostat")
    assert state.attributes[ATTR_HUMIDITY] == 40
    assert state.state == STATE_OFF


async def test_restore_state_uncoherence_case(hass: HomeAssistant) -> None:
    """Test restore from a strange state.

    - Turn the generic hygrostat off
    - Restart HA and restore state from DB
    """
    _mock_restore_cache(hass, humidity=40)

    calls = await _setup_switch(hass, False)
    _setup_sensor(hass, 35)
    await _setup_humidifier(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY)
    assert state.attributes[ATTR_HUMIDITY] == 40
    assert state.state == STATE_OFF
    assert len(calls) == 0

    calls = await _setup_switch(hass, False)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.state == STATE_OFF


async def _setup_humidifier(hass: HomeAssistant) -> None:
    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "dry_tolerance": 2,
                "wet_tolerance": 4,
                "away_humidity": 32,
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "device_class": "dehumidifier",
            }
        },
    )
    await hass.async_block_till_done()


def _mock_restore_cache(
    hass: HomeAssistant, humidity: int = 40, state: str = STATE_OFF
) -> None:
    mock_restore_cache(
        hass,
        (
            State(
                ENTITY,
                state,
                {
                    ATTR_ENTITY_ID: ENTITY,
                    ATTR_HUMIDITY: str(humidity),
                    ATTR_MODE: MODE_AWAY,
                },
            ),
        ),
    )


async def test_away_fixed_humidity_mode(hass: HomeAssistant) -> None:
    """Ensure retain of target humidity for normal mode."""
    _setup_sensor(hass, 45)
    await hass.async_block_till_done()
    await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test_hygrostat",
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "away_humidity": 32,
                "target_humidity": 40,
                "away_fixed": True,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("humidifier.test_hygrostat")
    assert state.attributes[ATTR_HUMIDITY] == 40
    assert state.attributes[ATTR_MODE] == MODE_NORMAL
    assert state.state == STATE_OFF

    # Switch to Away mode
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: "humidifier.test_hygrostat", ATTR_MODE: MODE_AWAY},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Target humidity changed to away_humidity
    state = hass.states.get("humidifier.test_hygrostat")
    assert state.attributes[ATTR_MODE] == MODE_AWAY
    assert state.attributes[ATTR_HUMIDITY] == 32
    assert state.attributes[ATTR_SAVED_HUMIDITY] == 40
    assert state.state == STATE_OFF

    # Change target humidity
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: "humidifier.test_hygrostat", ATTR_HUMIDITY: 42},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Current target humidity not changed
    state = hass.states.get("humidifier.test_hygrostat")
    assert state.attributes[ATTR_HUMIDITY] == 32
    assert state.attributes[ATTR_SAVED_HUMIDITY] == 42
    assert state.attributes[ATTR_MODE] == MODE_AWAY
    assert state.state == STATE_OFF

    # Return to Normal mode
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: "humidifier.test_hygrostat", ATTR_MODE: MODE_NORMAL},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Target humidity changed to away_humidity
    state = hass.states.get("humidifier.test_hygrostat")
    assert state.attributes[ATTR_HUMIDITY] == 42
    assert state.attributes[ATTR_SAVED_HUMIDITY] == 32
    assert state.attributes[ATTR_MODE] == MODE_NORMAL
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("setup_comp_1")
async def test_sensor_stale_duration(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test turn off on sensor stale."""

    humidifier_switch = "input_boolean.test"
    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test": None}}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        HUMIDIFIER_DOMAIN,
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "humidifier": humidifier_switch,
                "target_sensor": ENT_SENSOR,
                "initial_state": True,
                "sensor_stale_duration": {"minutes": 10},
            }
        },
    )
    await hass.async_block_till_done()

    _setup_sensor(hass, 23)
    await hass.async_block_till_done()

    assert hass.states.get(humidifier_switch).state == STATE_OFF

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: ENTITY, ATTR_HUMIDITY: 32},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(humidifier_switch).state == STATE_ON

    # Wait 11 minutes
    freezer.tick(datetime.timedelta(minutes=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # 11 minutes later, no news from the sensor : emergency cut off
    assert hass.states.get(humidifier_switch).state == STATE_OFF
    assert "emergency" in caplog.text

    # Updated value from sensor received (same value)
    _setup_sensor(hass, 23)
    await hass.async_block_till_done()

    # A new value has arrived, the humidifier should go ON
    assert hass.states.get(humidifier_switch).state == STATE_ON

    # Wait 11 minutes
    freezer.tick(datetime.timedelta(minutes=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # 11 minutes later, no news from the sensor : emergency cut off
    assert hass.states.get(humidifier_switch).state == STATE_OFF
    assert "emergency" in caplog.text

    # Updated value from sensor received (new value)
    _setup_sensor(hass, 24)
    await hass.async_block_till_done()

    # A new value has arrived, the humidifier should go ON
    assert hass.states.get(humidifier_switch).state == STATE_ON

    # Manual turn off
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(humidifier_switch).state == STATE_OFF

    # Wait another 11 minutes
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=22))
    await hass.async_block_till_done()

    # Still off
    assert hass.states.get(humidifier_switch).state == STATE_OFF

    # Updated value from sensor received
    _setup_sensor(hass, 22)
    await hass.async_block_till_done()

    # Not turning on by itself
    assert hass.states.get(humidifier_switch).state == STATE_OFF


async def test_device_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test for source entity device."""

    source_config_entry = MockConfigEntry()
    source_config_entry.add_to_hass(hass)
    source_device_entry = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={("switch", "identifier_test")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    source_entity = entity_registry.async_get_or_create(
        "switch",
        "test",
        "source",
        config_entry=source_config_entry,
        device_id=source_device_entry.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("switch.test_source") is not None

    helper_config_entry = MockConfigEntry(
        data={},
        domain=GENERIC_HYDROSTAT_DOMAIN,
        options={
            "device_class": "humidifier",
            "dry_tolerance": 2.0,
            "humidifier": "switch.test_source",
            "name": "Test",
            "target_sensor": ENT_SENSOR,
            "wet_tolerance": 4.0,
        },
        title="Test",
    )
    helper_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    helper_entity = entity_registry.async_get("humidifier.test")
    assert helper_entity is not None
    assert helper_entity.device_id == source_entity.device_id
