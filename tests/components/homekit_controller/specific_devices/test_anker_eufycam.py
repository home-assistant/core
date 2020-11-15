"""Test against characteristics captured from a eufycam."""

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_eufycam_setup(hass):
    """Test that a eufycam can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "anker_eufycam.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Check that the camera is correctly found and set up
    camera_id = "camera.eufycam2_0000"
    camera = entity_registry.async_get(camera_id)
    assert camera.unique_id == "homekit-A0000A000000000D-aid:4"

    camera_helper = Helper(
        hass,
        "camera.eufycam2_0000",
        pairing,
        accessories[0],
        config_entry,
    )

    camera_state = await camera_helper.poll_and_get_state()
    assert camera_state.attributes["friendly_name"] == "eufyCam2-0000"
    assert camera_state.state == "idle"
    assert camera_state.attributes["supported_features"] == 0

    device_registry = await hass.helpers.device_registry.async_get_registry()

    device = device_registry.async_get(camera.device_id)
    assert device.manufacturer == "Anker"
    assert device.name == "eufyCam2-0000"
    assert device.model == "T8113"
    assert device.sw_version == "1.6.7"

    # These cameras are via a bridge, so via should be set
    assert device.via_device_id is not None

    cameras_count = 0
    for state in hass.states.async_all():
        if state.entity_id.startswith("camera."):
            cameras_count += 1

    # There are multiple rtsp services, we only want to create 1
    # camera entity per accessory, not 1 camera per service.
    assert cameras_count == 3
