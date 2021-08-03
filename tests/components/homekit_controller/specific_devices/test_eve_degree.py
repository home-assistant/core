"""Make sure that Eve Degree (via Eve Extend) is enumerated properly."""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_eve_degree_setup(hass):
    """Test that the accessory can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "eve_degree.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    sensors = [
        (
            "sensor.eve_degree_aa11_temperature",
            "homekit-AA00A0A00000-22",
            "Eve Degree AA11 Temperature",
        ),
        (
            "sensor.eve_degree_aa11_humidity",
            "homekit-AA00A0A00000-27",
            "Eve Degree AA11 Humidity",
        ),
        (
            "sensor.eve_degree_aa11_air_pressure",
            "homekit-AA00A0A00000-aid:1-sid:30-cid:32",
            "Eve Degree AA11 - Air Pressure",
        ),
        (
            "sensor.eve_degree_aa11_battery",
            "homekit-AA00A0A00000-17",
            "Eve Degree AA11 Battery",
        ),
        (
            "number.eve_degree_aa11",
            "homekit-AA00A0A00000-aid:1-sid:30-cid:33",
            "Eve Degree AA11",
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
        assert device.manufacturer == "Elgato"
        assert device.name == "Eve Degree AA11"
        assert device.model == "Eve Degree 00AAA0000"
        assert device.sw_version == "1.2.8"
        assert device.via_device_id is None

        device_ids.add(entry.device_id)

    # All entities should be part of same device
    assert len(device_ids) == 1
