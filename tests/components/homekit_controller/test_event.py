"""Test homekit_controller stateless triggers."""

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.event import EventDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_test_component


def create_remote(accessory):
    """Define characteristics for a button (that is inn a group)."""
    service_label = accessory.add_service(ServicesTypes.SERVICE_LABEL)

    char = service_label.add_char(CharacteristicsTypes.SERVICE_LABEL_NAMESPACE)
    char.value = 1

    for i in range(4):
        button = accessory.add_service(ServicesTypes.STATELESS_PROGRAMMABLE_SWITCH)
        button.linked.append(service_label)

        char = button.add_char(CharacteristicsTypes.INPUT_EVENT)
        char.value = 0
        char.perms = ["pw", "pr", "ev"]

        char = button.add_char(CharacteristicsTypes.NAME)
        char.value = f"Button {i + 1}"

        char = button.add_char(CharacteristicsTypes.SERVICE_LABEL_INDEX)
        char.value = i

    battery = accessory.add_service(ServicesTypes.BATTERY_SERVICE)
    battery.add_char(CharacteristicsTypes.BATTERY_LEVEL)


def create_button(accessory):
    """Define a button (that is not in a group)."""
    button = accessory.add_service(ServicesTypes.STATELESS_PROGRAMMABLE_SWITCH)

    char = button.add_char(CharacteristicsTypes.INPUT_EVENT)
    char.value = 0
    char.perms = ["pw", "pr", "ev"]

    char = button.add_char(CharacteristicsTypes.NAME)
    char.value = "Button 1"

    battery = accessory.add_service(ServicesTypes.BATTERY_SERVICE)
    battery.add_char(CharacteristicsTypes.BATTERY_LEVEL)


def create_doorbell(accessory):
    """Define a button (that is not in a group)."""
    button = accessory.add_service(ServicesTypes.DOORBELL)

    char = button.add_char(CharacteristicsTypes.INPUT_EVENT)
    char.value = 0
    char.perms = ["pw", "pr", "ev"]

    char = button.add_char(CharacteristicsTypes.NAME)
    char.value = "Doorbell"

    battery = accessory.add_service(ServicesTypes.BATTERY_SERVICE)
    battery.add_char(CharacteristicsTypes.BATTERY_LEVEL)


async def test_remote(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test that remote is supported."""
    helper = await setup_test_component(hass, create_remote)

    entities = [
        ("event.testdevice_button_1", "Button 1"),
        ("event.testdevice_button_2", "Button 2"),
        ("event.testdevice_button_3", "Button 3"),
        ("event.testdevice_button_4", "Button 4"),
    ]

    for entity_id, service in entities:
        button = entity_registry.async_get(entity_id)

        assert button.original_device_class == EventDeviceClass.BUTTON
        assert button.capabilities["event_types"] == [
            "single_press",
            "double_press",
            "long_press",
        ]

        helper.pairing.testing.update_named_service(
            service, {CharacteristicsTypes.INPUT_EVENT: 0}
        )
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.attributes["event_type"] == "single_press"

        helper.pairing.testing.update_named_service(
            service, {CharacteristicsTypes.INPUT_EVENT: 1}
        )
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.attributes["event_type"] == "double_press"

        helper.pairing.testing.update_named_service(
            service, {CharacteristicsTypes.INPUT_EVENT: 2}
        )
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.attributes["event_type"] == "long_press"


async def test_button(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test that a button is correctly enumerated."""
    helper = await setup_test_component(hass, create_button)
    entity_id = "event.testdevice_button_1"

    button = entity_registry.async_get(entity_id)

    assert button.original_device_class == EventDeviceClass.BUTTON
    assert button.capabilities["event_types"] == [
        "single_press",
        "double_press",
        "long_press",
    ]

    helper.pairing.testing.update_named_service(
        "Button 1", {CharacteristicsTypes.INPUT_EVENT: 0}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "single_press"

    helper.pairing.testing.update_named_service(
        "Button 1", {CharacteristicsTypes.INPUT_EVENT: 1}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "double_press"

    helper.pairing.testing.update_named_service(
        "Button 1", {CharacteristicsTypes.INPUT_EVENT: 2}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "long_press"


async def test_doorbell(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that doorbell service is handled."""
    helper = await setup_test_component(hass, create_doorbell)
    entity_id = "event.testdevice_doorbell"

    doorbell = entity_registry.async_get(entity_id)

    assert doorbell.original_device_class == EventDeviceClass.DOORBELL
    assert doorbell.capabilities["event_types"] == [
        "single_press",
        "double_press",
        "long_press",
    ]

    helper.pairing.testing.update_named_service(
        "Doorbell", {CharacteristicsTypes.INPUT_EVENT: 0}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "single_press"

    helper.pairing.testing.update_named_service(
        "Doorbell", {CharacteristicsTypes.INPUT_EVENT: 1}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "double_press"

    helper.pairing.testing.update_named_service(
        "Doorbell", {CharacteristicsTypes.INPUT_EVENT: 2}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "long_press"
