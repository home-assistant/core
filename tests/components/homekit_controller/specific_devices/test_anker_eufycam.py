"""Test against characteristics captured from a eufycam."""
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_eufycam_setup(hass: HomeAssistant) -> None:
    """Test that a eufycam can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "anker_eufycam.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="eufy HomeBase2-0AAA",
            model="T8010",
            manufacturer="Anker",
            sw_version="2.1.6",
            hw_version="2.0.0",
            serial_number="A0000A000000000A",
            devices=[
                DeviceTestInfo(
                    name="eufyCam2-0000",
                    model="T8113",
                    manufacturer="Anker",
                    sw_version="1.6.7",
                    hw_version="1.0.0",
                    serial_number="A0000A000000000D",
                    unique_id="00:00:00:00:00:00:aid:4",
                    devices=[],
                    entities=[
                        EntityTestInfo(
                            entity_id="camera.eufycam2_0000",
                            friendly_name="eufyCam2-0000",
                            unique_id="00:00:00:00:00:00_4",
                            state="idle",
                        ),
                    ],
                ),
            ],
            entities=[],
        ),
    )

    # There are multiple rtsp services, we only want to create 1
    # camera entity per accessory, not 1 camera per service.
    cameras_count = 0
    for state in hass.states.async_all():
        if state.entity_id.startswith("camera."):
            cameras_count += 1
    assert cameras_count == 3
