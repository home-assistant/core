"""Basic checks for HomeKit Humidifier/Dehumidifier."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.humidifier import DOMAIN
from homeassistant.components.humidifier.const import MODE_AUTO, MODE_NORMAL

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


def create_humidifier_service(accessory):
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

    return service


def create_dehumidifier_service(accessory):
    """Define a dehumidifier characteristics as per page 219 of HAP spec."""
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

    targ_state = service.add_char(
        CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD
    )
    targ_state.value = 0

    return service


async def test_humidifier_active_state(hass, utcnow):
    """Test that we can turn a HomeKit humidifier on and off again."""
    helper = await setup_test_component(hass, create_humidifier_service)

    await hass.services.async_call(
        DOMAIN, "turn_on", {"entity_id": helper.entity_id}, blocking=True
    )

    assert helper.characteristics[ACTIVE].value == 1

    await hass.services.async_call(
        DOMAIN, "turn_off", {"entity_id": helper.entity_id}, blocking=True
    )

    assert helper.characteristics[ACTIVE].value == 0


async def test_dehumidifier_active_state(hass, utcnow):
    """Test that we can turn a HomeKit dehumidifier on and off again."""
    helper = await setup_test_component(hass, create_dehumidifier_service)

    await hass.services.async_call(
        DOMAIN, "turn_on", {"entity_id": helper.entity_id}, blocking=True
    )

    assert helper.characteristics[ACTIVE].value == 1

    await hass.services.async_call(
        DOMAIN, "turn_off", {"entity_id": helper.entity_id}, blocking=True
    )

    assert helper.characteristics[ACTIVE].value == 0


async def test_humidifier_read_humidity(hass, utcnow):
    """Test that we can read the state of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, create_humidifier_service)

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

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 3
    state = await helper.poll_and_get_state()
    assert state.attributes["humidity"] == 10


async def test_dehumidifier_read_humidity(hass, utcnow):
    """Test that we can read the state of a HomeKit dehumidifier accessory."""
    helper = await setup_test_component(hass, create_dehumidifier_service)

    helper.characteristics[ACTIVE].value = True
    helper.characteristics[RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD].value = 75
    state = await helper.poll_and_get_state()
    assert state.state == "on"
    assert state.attributes["humidity"] == 75

    helper.characteristics[ACTIVE].value = False
    helper.characteristics[RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD].value = 40
    state = await helper.poll_and_get_state()
    assert state.state == "off"
    assert state.attributes["humidity"] == 40

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 2
    state = await helper.poll_and_get_state()
    assert state.attributes["humidity"] == 40


async def test_humidifier_set_humidity(hass, utcnow):
    """Test that we can set the state of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, create_humidifier_service)

    await hass.services.async_call(
        DOMAIN,
        "set_humidity",
        {"entity_id": helper.entity_id, "humidity": 20},
        blocking=True,
    )
    assert helper.characteristics[RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD].value == 20


async def test_dehumidifier_set_humidity(hass, utcnow):
    """Test that we can set the state of a HomeKit dehumidifier accessory."""
    helper = await setup_test_component(hass, create_dehumidifier_service)

    await hass.services.async_call(
        DOMAIN,
        "set_humidity",
        {"entity_id": helper.entity_id, "humidity": 20},
        blocking=True,
    )
    assert helper.characteristics[RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD].value == 20


async def test_humidifier_set_mode(hass, utcnow):
    """Test that we can set the mode of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, create_humidifier_service)

    await hass.services.async_call(
        DOMAIN,
        "set_mode",
        {"entity_id": helper.entity_id, "mode": MODE_AUTO},
        blocking=True,
    )
    assert helper.characteristics[TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE].value == 0
    assert helper.characteristics[ACTIVE].value == 1

    await hass.services.async_call(
        DOMAIN,
        "set_mode",
        {"entity_id": helper.entity_id, "mode": MODE_NORMAL},
        blocking=True,
    )
    assert helper.characteristics[TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE].value == 1
    assert helper.characteristics[ACTIVE].value == 1


async def test_dehumidifier_set_mode(hass, utcnow):
    """Test that we can set the mode of a HomeKit dehumidifier accessory."""
    helper = await setup_test_component(hass, create_dehumidifier_service)

    await hass.services.async_call(
        DOMAIN,
        "set_mode",
        {"entity_id": helper.entity_id, "mode": MODE_AUTO},
        blocking=True,
    )
    assert helper.characteristics[TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE].value == 0
    assert helper.characteristics[ACTIVE].value == 1

    await hass.services.async_call(
        DOMAIN,
        "set_mode",
        {"entity_id": helper.entity_id, "mode": MODE_NORMAL},
        blocking=True,
    )
    assert helper.characteristics[TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE].value == 2
    assert helper.characteristics[ACTIVE].value == 1


async def test_humidifier_read_only_mode(hass, utcnow):
    """Test that we can read the state of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, create_humidifier_service)

    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "auto"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 2
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 3
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"


async def test_dehumidifier_read_only_mode(hass, utcnow):
    """Test that we can read the state of a HomeKit dehumidifier accessory."""
    helper = await setup_test_component(hass, create_dehumidifier_service)

    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "auto"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 2
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 3
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"


async def test_humidifier_target_humidity_modes(hass, utcnow):
    """Test that we can read the state of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, create_humidifier_service)

    helper.characteristics[RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD].value = 37
    helper.characteristics[RELATIVE_HUMIDITY_CURRENT].value = 51
    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 1

    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "auto"
    assert state.attributes["humidity"] == 37

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 3
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 37

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 2
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 37

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 37


async def test_dehumidifier_target_humidity_modes(hass, utcnow):
    """Test that we can read the state of a HomeKit dehumidifier accessory."""
    helper = await setup_test_component(hass, create_dehumidifier_service)

    helper.characteristics[RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD].value = 73
    helper.characteristics[RELATIVE_HUMIDITY_CURRENT].value = 51
    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 1

    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "auto"
    assert state.attributes["humidity"] == 73

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 3
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 73

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 2
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 73

    helper.characteristics[CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 73
