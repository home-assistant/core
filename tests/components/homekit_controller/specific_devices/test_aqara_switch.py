"""
Regression tests for Aqara AR004.

This device has a non-standard programmable stateless switch service that has a
service-label-index despite not being linked to a service-label.

https://github.com/home-assistant/core/pull/39090
"""

from homeassistant.helpers import entity_registry as er

from tests.common import assert_lists_same, async_get_device_automations
from tests.components.homekit_controller.common import (
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_aqara_switch_setup(hass):
    """Test that a Aqara Switch can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "aqara_switch.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)

    battery_id = "sensor.programmable_switch_battery"
    battery = entity_registry.async_get(battery_id)
    assert battery.unique_id == "homekit-111a1111a1a111-5"

    # The fixture file has 1 button and a battery

    expected = [
        {
            "device_id": battery.device_id,
            "domain": "sensor",
            "entity_id": "sensor.programmable_switch_battery",
            "platform": "device",
            "type": "battery_level",
        }
    ]

    for subtype in ("single_press", "double_press", "long_press"):
        expected.append(
            {
                "device_id": battery.device_id,
                "domain": "homekit_controller",
                "platform": "device",
                "type": "button1",
                "subtype": subtype,
            }
        )

    triggers = await async_get_device_automations(hass, "trigger", battery.device_id)
    assert_lists_same(triggers, expected)
