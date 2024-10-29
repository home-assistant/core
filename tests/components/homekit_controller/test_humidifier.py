"""Basic checks for HomeKit Humidifier/Dehumidifier."""

from collections.abc import Callable

from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.humidifier import (
    DOMAIN as HUMIDIFIER_DOMAIN,
    MODE_AUTO,
    MODE_NORMAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_test_component


def create_humidifier_service(accessory: Accessory) -> Service:
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


def create_dehumidifier_service(accessory: Accessory) -> Service:
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


async def test_humidifier_active_state(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can turn a HomeKit humidifier on and off again."""
    helper = await setup_test_component(hass, get_next_aid(), create_humidifier_service)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN, "turn_on", {"entity_id": helper.entity_id}, blocking=True
    )

    helper.async_assert_service_values(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {CharacteristicsTypes.ACTIVE: 1},
    )

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN, "turn_off", {"entity_id": helper.entity_id}, blocking=True
    )

    helper.async_assert_service_values(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {CharacteristicsTypes.ACTIVE: 0},
    )


async def test_dehumidifier_active_state(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can turn a HomeKit dehumidifier on and off again."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_dehumidifier_service
    )

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN, "turn_on", {"entity_id": helper.entity_id}, blocking=True
    )

    helper.async_assert_service_values(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {CharacteristicsTypes.ACTIVE: 1},
    )

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN, "turn_off", {"entity_id": helper.entity_id}, blocking=True
    )

    helper.async_assert_service_values(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {CharacteristicsTypes.ACTIVE: 0},
    )


async def test_humidifier_read_humidity(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, get_next_aid(), create_humidifier_service)

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.ACTIVE: True,
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD: 75,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT: 45,
        },
    )
    assert state.state == "on"
    assert state.attributes["humidity"] == 75
    assert state.attributes["current_humidity"] == 45

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.ACTIVE: False,
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD: 10,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT: 30,
        },
    )
    assert state.state == "off"
    assert state.attributes["humidity"] == 10
    assert state.attributes["current_humidity"] == 30

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 3,
        },
    )
    assert state.attributes["humidity"] == 10
    assert state.attributes["current_humidity"] == 30
    assert state.state == "off"


async def test_dehumidifier_read_humidity(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit dehumidifier accessory."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_dehumidifier_service
    )

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.ACTIVE: True,
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD: 75,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT: 45,
        },
    )
    assert state.state == "on"
    assert state.attributes["humidity"] == 75
    assert state.attributes["current_humidity"] == 45

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.ACTIVE: False,
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD: 40,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT: 39,
        },
    )
    assert state.state == "off"
    assert state.attributes["humidity"] == 40
    assert state.attributes["current_humidity"] == 39

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 2,
        },
    )
    assert state.attributes["humidity"] == 40


async def test_humidifier_set_humidity(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can set the state of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, get_next_aid(), create_humidifier_service)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        "set_humidity",
        {"entity_id": helper.entity_id, "humidity": 20},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD: 20},
    )


async def test_dehumidifier_set_humidity(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can set the state of a HomeKit dehumidifier accessory."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_dehumidifier_service
    )

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        "set_humidity",
        {"entity_id": helper.entity_id, "humidity": 20},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD: 20},
    )


async def test_humidifier_set_mode(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can set the mode of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, get_next_aid(), create_humidifier_service)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        "set_mode",
        {"entity_id": helper.entity_id, "mode": MODE_AUTO},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.ACTIVE: 1,
            CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE: 0,
        },
    )

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        "set_mode",
        {"entity_id": helper.entity_id, "mode": MODE_NORMAL},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.ACTIVE: 1,
            CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE: 1,
        },
    )


async def test_dehumidifier_set_mode(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can set the mode of a HomeKit dehumidifier accessory."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_dehumidifier_service
    )

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        "set_mode",
        {"entity_id": helper.entity_id, "mode": MODE_AUTO},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.ACTIVE: 1,
            CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE: 0,
        },
    )

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        "set_mode",
        {"entity_id": helper.entity_id, "mode": MODE_NORMAL},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.ACTIVE: 1,
            CharacteristicsTypes.TARGET_HUMIDIFIER_DEHUMIDIFIER_STATE: 2,
        },
    )


async def test_humidifier_read_only_mode(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, get_next_aid(), create_humidifier_service)

    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 0,
        },
    )
    assert state.attributes["mode"] == "normal"

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 1,
        },
    )
    assert state.attributes["mode"] == "auto"

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 2,
        },
    )
    assert state.attributes["mode"] == "normal"

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 3,
        },
    )
    assert state.attributes["mode"] == "normal"


async def test_dehumidifier_read_only_mode(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit dehumidifier accessory."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_dehumidifier_service
    )

    state = await helper.poll_and_get_state()
    assert state.attributes["mode"] == "normal"

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 0,
        },
    )
    assert state.attributes["mode"] == "normal"

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 1,
        },
    )
    assert state.attributes["mode"] == "auto"

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 2,
        },
    )
    assert state.attributes["mode"] == "normal"

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 3,
        },
    )
    assert state.attributes["mode"] == "normal"


async def test_humidifier_target_humidity_modes(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit humidifier accessory."""
    helper = await setup_test_component(hass, get_next_aid(), create_humidifier_service)

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.RELATIVE_HUMIDITY_HUMIDIFIER_THRESHOLD: 37,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT: 51,
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 1,
        },
    )
    assert state.attributes["mode"] == "auto"
    assert state.attributes["humidity"] == 37
    assert state.attributes["current_humidity"] == 51

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 3,
        },
    )
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 37
    assert state.attributes["current_humidity"] == 51

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 2,
        },
    )
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 37

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 0,
        },
    )
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 37


async def test_dehumidifier_target_humidity_modes(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit dehumidifier accessory."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_dehumidifier_service
    )

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.RELATIVE_HUMIDITY_DEHUMIDIFIER_THRESHOLD: 73,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT: 51,
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 1,
        },
    )
    assert state.attributes["mode"] == "auto"
    assert state.attributes["humidity"] == 73
    assert state.attributes["current_humidity"] == 51

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 3,
        },
    )
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 73
    assert state.attributes["current_humidity"] == 51

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 2,
        },
    )
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 73
    assert state.attributes["current_humidity"] == 51

    state = await helper.async_update(
        ServicesTypes.HUMIDIFIER_DEHUMIDIFIER,
        {
            CharacteristicsTypes.CURRENT_HUMIDIFIER_DEHUMIDIFIER_STATE: 0,
        },
    )
    assert state.attributes["mode"] == "normal"
    assert state.attributes["humidity"] == 73
    assert state.attributes["current_humidity"] == 51


async def test_migrate_entity_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    get_next_aid: Callable[[], int],
) -> None:
    """Test that we can migrate humidifier entity ids."""
    aid = get_next_aid()

    humidifier_entry = entity_registry.async_get_or_create(
        "humidifier",
        "homekit_controller",
        f"homekit-00:00:00:00:00:00-{aid}-8",
    )
    await setup_test_component(hass, aid, create_humidifier_service)
    assert (
        entity_registry.async_get(humidifier_entry.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8"
    )
