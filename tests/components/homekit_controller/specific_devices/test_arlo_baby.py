"""Make sure that an Arlo Baby can be setup."""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_arlo_baby_setup(hass):
    """Test that an Arlo Baby can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "arlo_baby.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    sensors = [
        (
            "camera.arlobabya0",
            "homekit-00A0000000000-aid:1",
            "ArloBabyA0",
        ),
        (
            "binary_sensor.arlobabya0",
            "homekit-00A0000000000-500",
            "ArloBabyA0",
        ),
        (
            "sensor.arlobabya0_battery",
            "homekit-00A0000000000-700",
            "ArloBabyA0 Battery",
        ),
        (
            "sensor.arlobabya0_humidity",
            "homekit-00A0000000000-900",
            "ArloBabyA0 Humidity",
        ),
        (
            "sensor.arlobabya0_temperature",
            "homekit-00A0000000000-1000",
            "ArloBabyA0 Temperature",
        ),
        (
            "sensor.arlobabya0_air_quality",
            "homekit-00A0000000000-aid:1-sid:800-cid:802",
            "ArloBabyA0 - Air Quality",
        ),
        (
            "light.arlobabya0",
            "homekit-00A0000000000-1100",
            "ArloBabyA0",
        ),
    ]

    device_ids = set()

    for (entity_id, unique_id, friendly_name) in sensors:
        entry = entity_registry.async_get(entity_id)
        assert entry.unique_id == unique_id

        helper = Helper(
            hass,
            entity_id,
            pairing,
            accessories[0],
            config_entry,
        )
        state = await helper.poll_and_get_state()
        assert state.attributes["friendly_name"] == friendly_name

        device = device_registry.async_get(entry.device_id)
        assert device.manufacturer == "Netgear, Inc"
        assert device.name == "ArloBabyA0"
        assert device.model == "ABC1000"
        assert device.sw_version == "1.10.931"
        assert device.via_device_id is None

        device_ids.add(entry.device_id)

    # All entities should be part of same device
    assert len(device_ids) == 1
