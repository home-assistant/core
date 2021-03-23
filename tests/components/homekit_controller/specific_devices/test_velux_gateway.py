"""
Test against characteristics captured from a Velux Gateway.

https://github.com/home-assistant/core/issues/44314
"""

from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_simpleconnect_cover_setup(hass):
    """Test that a velux gateway can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "velux_gateway.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)

    # Check that the cover is correctly found and set up
    cover_id = "cover.velux_window"
    cover = entity_registry.async_get(cover_id)
    assert cover.unique_id == "homekit-1111111a114a111a-8"

    cover_helper = Helper(
        hass,
        cover_id,
        pairing,
        accessories[0],
        config_entry,
    )

    cover_state = await cover_helper.poll_and_get_state()
    assert cover_state.attributes["friendly_name"] == "VELUX Window"
    assert cover_state.state == "closed"
    assert cover_state.attributes["supported_features"] == (
        SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_OPEN
    )

    # Check that one of the sensors is correctly found and set up
    sensor_id = "sensor.velux_sensor_temperature"
    sensor = entity_registry.async_get(sensor_id)
    assert sensor.unique_id == "homekit-a11b111-8"

    sensor_helper = Helper(
        hass,
        sensor_id,
        pairing,
        accessories[0],
        config_entry,
    )

    sensor_state = await sensor_helper.poll_and_get_state()
    assert sensor_state.attributes["friendly_name"] == "VELUX Sensor Temperature"
    assert sensor_state.state == "18.9"

    # The cover and sensor are different devices (accessories) attached to the same bridge
    assert cover.device_id != sensor.device_id

    device_registry = dr.async_get(hass)

    device = device_registry.async_get(cover.device_id)
    assert device.manufacturer == "VELUX"
    assert device.name == "VELUX Window"
    assert device.model == "VELUX Window"
    assert device.sw_version == "48"

    bridge = device_registry.async_get(device.via_device_id)
    assert bridge.manufacturer == "VELUX"
    assert bridge.name == "VELUX Gateway"
    assert bridge.model == "VELUX Gateway"
    assert bridge.sw_version == "70"
