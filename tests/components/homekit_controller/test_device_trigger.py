"""Test homekit_controller stateless triggers."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.homekit_controller.const import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import (
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa
from tests.components.homekit_controller.common import setup_test_component


# pylint: disable=redefined-outer-name
@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


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


async def test_enumerate_remote(hass, utcnow):
    """Test that remote is correctly enumerated."""
    await setup_test_component(hass, create_remote)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entry = entity_registry.async_get("sensor.testdevice_battery")

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    expected = [
        {
            "device_id": device.id,
            "domain": "sensor",
            "entity_id": "sensor.testdevice_battery",
            "platform": "device",
            "type": "battery_level",
        }
    ]

    for button in ("button1", "button2", "button3", "button4"):
        for subtype in ("single_press", "double_press", "long_press"):
            expected.append(
                {
                    "device_id": device.id,
                    "domain": "homekit_controller",
                    "platform": "device",
                    "type": button,
                    "subtype": subtype,
                }
            )

    triggers = await async_get_device_automations(hass, "trigger", device.id)
    assert_lists_same(triggers, expected)


async def test_enumerate_button(hass, utcnow):
    """Test that a button is correctly enumerated."""
    await setup_test_component(hass, create_button)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entry = entity_registry.async_get("sensor.testdevice_battery")

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    expected = [
        {
            "device_id": device.id,
            "domain": "sensor",
            "entity_id": "sensor.testdevice_battery",
            "platform": "device",
            "type": "battery_level",
        }
    ]

    for subtype in ("single_press", "double_press", "long_press"):
        expected.append(
            {
                "device_id": device.id,
                "domain": "homekit_controller",
                "platform": "device",
                "type": "button1",
                "subtype": subtype,
            }
        )

    triggers = await async_get_device_automations(hass, "trigger", device.id)
    assert_lists_same(triggers, expected)


async def test_enumerate_doorbell(hass, utcnow):
    """Test that a button is correctly enumerated."""
    await setup_test_component(hass, create_doorbell)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entry = entity_registry.async_get("sensor.testdevice_battery")

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    expected = [
        {
            "device_id": device.id,
            "domain": "sensor",
            "entity_id": "sensor.testdevice_battery",
            "platform": "device",
            "type": "battery_level",
        }
    ]

    for subtype in ("single_press", "double_press", "long_press"):
        expected.append(
            {
                "device_id": device.id,
                "domain": "homekit_controller",
                "platform": "device",
                "type": "doorbell",
                "subtype": subtype,
            }
        )

    triggers = await async_get_device_automations(hass, "trigger", device.id)
    assert_lists_same(triggers, expected)


async def test_handle_events(hass, utcnow, calls):
    """Test that events are handled."""
    helper = await setup_test_component(hass, create_remote)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entry = entity_registry.async_get("sensor.testdevice_battery")

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "alias": "single_press",
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "button1",
                        "subtype": "single_press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{ trigger.platform}} - "
                                "{{ trigger.type }} - {{ trigger.subtype }}"
                            )
                        },
                    },
                },
                {
                    "alias": "long_press",
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "button2",
                        "subtype": "long_press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{ trigger.platform}} - "
                                "{{ trigger.type }} - {{ trigger.subtype }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Make sure first automation (only) fires for single press
    helper.pairing.testing.update_named_service(
        "Button 1", {CharacteristicsTypes.INPUT_EVENT: 0}
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "device - button1 - single_press"

    # Make sure automation doesn't trigger for long press
    helper.pairing.testing.update_named_service(
        "Button 1", {CharacteristicsTypes.INPUT_EVENT: 1}
    )

    await hass.async_block_till_done()
    assert len(calls) == 1

    # Make sure automation doesn't trigger for double press
    helper.pairing.testing.update_named_service(
        "Button 1", {CharacteristicsTypes.INPUT_EVENT: 2}
    )

    await hass.async_block_till_done()
    assert len(calls) == 1

    # Make sure second automation fires for long press
    helper.pairing.testing.update_named_service(
        "Button 2", {CharacteristicsTypes.INPUT_EVENT: 2}
    )

    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "device - button2 - long_press"

    # Turn the automations off
    await hass.services.async_call(
        "automation",
        "turn_off",
        {"entity_id": "automation.long_press"},
        blocking=True,
    )

    await hass.services.async_call(
        "automation",
        "turn_off",
        {"entity_id": "automation.single_press"},
        blocking=True,
    )

    # Make sure event no longer fires
    helper.pairing.testing.update_named_service(
        "Button 2", {CharacteristicsTypes.INPUT_EVENT: 2}
    )

    await hass.async_block_till_done()
    assert len(calls) == 2
