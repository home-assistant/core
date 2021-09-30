"""
Regression tests for Netamo Doorbell.

https://github.com/home-assistant/core/issues/44596
"""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import assert_lists_same, async_get_device_automations
from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_netamo_doorbell_setup(hass):
    """Test that a Netamo Doorbell can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "netamo_doorbell.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)

    # Check that the camera is correctly found and set up
    doorbell_id = "camera.netatmo_doorbell_g738658"
    doorbell = entity_registry.async_get(doorbell_id)
    assert doorbell.unique_id == "homekit-g738658-aid:1"

    camera_helper = Helper(
        hass,
        "camera.netatmo_doorbell_g738658",
        pairing,
        accessories[0],
        config_entry,
    )
    camera_helper = await camera_helper.poll_and_get_state()
    assert camera_helper.attributes["friendly_name"] == "Netatmo-Doorbell-g738658"

    device_registry = dr.async_get(hass)

    device = device_registry.async_get(doorbell.device_id)
    assert device.manufacturer == "Netatmo"
    assert device.name == "Netatmo-Doorbell-g738658"
    assert device.model == "Netatmo Doorbell"
    assert device.sw_version == "80.0.0"
    assert device.via_device_id is None

    # The fixture file has 1 button
    expected = []
    for subtype in ("single_press", "double_press", "long_press"):
        expected.append(
            {
                "device_id": doorbell.device_id,
                "domain": "homekit_controller",
                "platform": "device",
                "type": "doorbell",
                "subtype": subtype,
            }
        )

    for type in ("no_motion", "motion"):
        expected.append(
            {
                "device_id": doorbell.device_id,
                "domain": "binary_sensor",
                "entity_id": "binary_sensor.netatmo_doorbell_g738658",
                "platform": "device",
                "type": type,
            }
        )

    triggers = await async_get_device_automations(hass, "trigger", doorbell.device_id)
    assert_lists_same(triggers, expected)
