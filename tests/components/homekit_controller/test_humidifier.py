"""Basic checks for HomeKit Humidifier/Dehumidifier."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.humidifier import DOMAIN

from tests.components.homekit_controller.common import setup_test_component

ACTIVE = ("humidifier-dehumidifier", "active")
CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE = (
    "humidifier-dehumidifier",
    "humidifier-dehumidifier.state.current",
)
TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE = (
    "humidifier-dehumidifier",
    "humidifier-dehumidifier.state.target",
)
RELATIVE_HUMIDITY_CURRENT = ("humidifier-dehumidifier", "relative-humidity.current")
RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD = (
    "humidifier-dehumidifier",
    "relative-humidity.humidifier-threshold",
)
RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD = (
    "humidifier-dehumidifier",
    "relative-humidity.dehumidifier-threshold",
)


def create_humidifier_dehumidifier_service(accessory):
    """Define a humidifier characteristics as per page 219 of HAP spec."""
    service = accessory.add_service(ServicesTypes.HUMIDIFIER_DEHUMIDIFIER)

    service.add_char(CharacteristicsTypes.ACTIVE, value=False)

    cur_state = service.add_char(CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT)
    cur_state.value = 0

    cur_state = service.add_char(
        CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE
    )
    cur_state.value = -1

    targ_state = service.add_char(
        CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE
    )
    targ_state.value = 0

    cur_state = service.add_char(
        CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD
    )
    cur_state.value = 0

    targ_state = service.add_char(
        CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
    )
    targ_state.value = 0

    return service


async def test_humidifier_active_state(hass, utcnow):
    """Test that we can turn a HomeKit humidifier on and off again."""
    helper = await setup_test_component(hass, create_humidifier_dehumidifier_service)

    await hass.services.async_call(
        DOMAIN, "turn_on", {"entity_id": "humidifier.testdevice"}, blocking=True
    )

    assert helper.characteristics[ACTIVE].value == 1

    await hass.services.async_call(
        DOMAIN, "turn_off", {"entity_id": "humidifier.testdevice"}, blocking=True
    )

    assert helper.characteristics[ACTIVE].value == 0


async def test_humidifier_read_humidity(hass, utcnow):
    """Test that we can read the state of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, create_humidifier_dehumidifier_service)

    helper.characteristics[ACTIVE].value = True
    helper.characteristics[RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD].value = 75
    state = await helper.poll_and_get_state()
    assert state.state == "on"
    assert state.attributes["humidity"] == 75

    helper.characteristics[ACTIVE].value = False
    helper.characteristics[RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == "off"
    assert state.attributes["humidity"] == 10


async def test_humidifier_read_only_mode(hass, utcnow):
    """Test that we can read the state of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, create_humidifier_dehumidifier_service)

    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "unknown"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "off"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "auto"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 2
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "humidifying"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 3
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "dehumidifying"


async def test_humidifier_target_humidity_modes(hass, utcnow):
    """Test that we can read the state of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, create_humidifier_dehumidifier_service)

    helper.characteristics[RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD].value = 37
    helper.characteristics[RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD].value = 73
    helper.characteristics[RELATIVE_HUMIDITY_CURRENT].value = 51
    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 1

    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "auto"
    assert state.attributes["humidity"] == 37
    assert state.attributes["current_humidity"] == 51
    assert state.attributes["humidifier_threshold"] == 37
    assert state.attributes["dehumidifier_threshold"] == 73

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 3
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "dehumidifying"
    assert state.attributes["humidity"] == 73

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 2
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "humidifying"
    assert state.attributes["humidity"] == 37

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "off"
    assert state.attributes["humidity"] == 37
