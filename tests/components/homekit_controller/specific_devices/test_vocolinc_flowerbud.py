"""
Test against characteristics captured from a VOCOLinc Flowerbud.

https://github.com/home-assistant/core/issues/26180
"""
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

VOCOLINC_HUMIDIFIER_SPRAY_LEVEL = (
    "humidifier-dehumidifier",
    f"Unknown Characteristic {CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL}",
)


def create_diffuser_service(accessory):
    """Define a diffuser accessory with VOCOLinc vendor specific characteristics."""
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
        CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL
    )
    targ_state.value = 0

    return service


async def test_diffuser_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit diffuser accessory."""
    helper = await setup_test_component(hass, create_diffuser_service)

    helper.characteristics[VOCOLINC_HUMIDIFIER_SPRAY_LEVEL].value = 5
    state = await helper.poll_and_get_state()
    assert state.attributes["humidity"] == 0

    helper.characteristics[ACTIVE].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["humidity"] == 100

    helper.characteristics[VOCOLINC_HUMIDIFIER_SPRAY_LEVEL].value = 2
    state = await helper.poll_and_get_state()
    assert state.attributes["humidity"] == 40

    helper.characteristics[ACTIVE].value = 0
    state = await helper.poll_and_get_state()
    assert state.attributes["humidity"] == 0


async def test_diffuser_set_state(hass, utcnow):
    """Test that we can set the state of a HomeKit diffuser accessory."""
    helper = await setup_test_component(hass, create_diffuser_service)

    await hass.services.async_call(
        DOMAIN,
        "set_humidity",
        {"entity_id": helper.entity_id, "humidity": 20},
        blocking=True,
    )
    assert helper.characteristics[VOCOLINC_HUMIDIFIER_SPRAY_LEVEL].value == 1

    await hass.services.async_call(
        DOMAIN,
        "set_humidity",
        {"entity_id": helper.entity_id, "humidity": 60},
        blocking=True,
    )
    assert helper.characteristics[VOCOLINC_HUMIDIFIER_SPRAY_LEVEL].value == 3

    await hass.services.async_call(
        DOMAIN,
        "turn_off",
        {"entity_id": helper.entity_id},
        blocking=True,
    )
    assert helper.characteristics[ACTIVE].value == 0

    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {"entity_id": helper.entity_id},
        blocking=True,
    )
    assert helper.characteristics[ACTIVE].value == 1

    await hass.services.async_call(
        DOMAIN,
        "set_humidity",
        {"entity_id": helper.entity_id, "humidity": 19},
        blocking=True,
    )
    assert helper.characteristics[ACTIVE].value == 0
