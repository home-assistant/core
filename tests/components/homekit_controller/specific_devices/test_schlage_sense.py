"""Make sure that Schlage Sense is enumerated properly."""
from homeassistant.core import HomeAssistant

from ..common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_schlage_sense_setup(hass: HomeAssistant) -> None:
    """Test that the accessory can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "schlage_sense.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="SENSE  ",
            model="BE479CAM619",
            manufacturer="Schlage ",
            sw_version="004.027.000",
            hw_version="1.3.0",
            serial_number="AAAAAAA000",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="lock.sense_lock_mechanism",
                    friendly_name="SENSE   Lock Mechanism",
                    unique_id="00:00:00:00:00:00_1_30",
                    supported_features=0,
                    state="unknown",
                ),
            ],
        ),
    )
