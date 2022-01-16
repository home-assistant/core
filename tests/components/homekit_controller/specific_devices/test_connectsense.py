"""Make sure that ConnectSense Smart Outlet2 / In-Wall Outlet is enumerated properly."""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.components.homekit_controller.common import (
    Helper,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_connectsense_setup(hass):
    """Test that the accessory can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "connectsense.json")
    config_entry, pairing = await setup_test_accessories(hass, accessories)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    entities = [
        (
            "sensor.inwall_outlet_0394de_real_time_current",
            "homekit-1020301376-aid:1-sid:13-cid:18",
            "InWall Outlet-0394DE - Real Time Current",
        ),
        (
            "sensor.inwall_outlet_0394de_real_time_energy",
            "homekit-1020301376-aid:1-sid:13-cid:19",
            "InWall Outlet-0394DE - Real Time Energy",
        ),
        (
            "sensor.inwall_outlet_0394de_energy_kwh",
            "homekit-1020301376-aid:1-sid:13-cid:20",
            "InWall Outlet-0394DE - Energy kWh",
        ),
        (
            "switch.inwall_outlet_0394de",
            "homekit-1020301376-13",
            "InWall Outlet-0394DE",
        ),
        (
            "sensor.inwall_outlet_0394de_real_time_current_2",
            "homekit-1020301376-aid:1-sid:25-cid:30",
            "InWall Outlet-0394DE - Real Time Current",
        ),
        (
            "sensor.inwall_outlet_0394de_real_time_energy_2",
            "homekit-1020301376-aid:1-sid:25-cid:31",
            "InWall Outlet-0394DE - Real Time Energy",
        ),
        (
            "sensor.inwall_outlet_0394de_energy_kwh_2",
            "homekit-1020301376-aid:1-sid:25-cid:32",
            "InWall Outlet-0394DE - Energy kWh",
        ),
        (
            "switch.inwall_outlet_0394de_2",
            "homekit-1020301376-25",
            "InWall Outlet-0394DE",
        ),
    ]

    device_ids = set()

    for (entity_id, unique_id, friendly_name) in entities:
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
        assert device.manufacturer == "ConnectSense"
        assert device.name == "InWall Outlet-0394DE"
        assert device.model == "CS-IWO"
        assert device.sw_version == "1.0.0"
        assert device.via_device_id is None

        device_ids.add(entry.device_id)

    # All entities should be part of same device
    assert len(device_ids) == 1
