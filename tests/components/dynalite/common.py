"""Common functions for tests."""
from asynctest import Mock, call, patch

from homeassistant.components import dynalite
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

ATTR_SERVICE = "service"
ATTR_METHOD = "method"
ATTR_ARGS = "args"


def create_mock_device(platform, spec):
    """Create a dynalite mock device for a platform according to a spec."""
    device = Mock(spec=spec)
    device.category = platform
    device.unique_id = "UNIQUE"
    device.name = "NAME"
    device.device_class = "Device Class"
    device.device_info = {
        "identifiers": {(dynalite.DOMAIN, device.unique_id)},
        "name": device.name,
        "manufacturer": "Dynalite",
    }
    return device


async def get_entry_id_from_hass(hass):
    """Get the config entry id from hass."""
    ent_reg = await entity_registry.async_get_registry(hass)
    assert ent_reg
    conf_entries = hass.config_entries.async_entries(dynalite.DOMAIN)
    assert len(conf_entries) == 1
    return conf_entries[0].entry_id


async def create_entity_from_device(hass, device):
    """Set up the component and platform and create a light based on the device provided."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        assert await async_setup_component(
            hass,
            dynalite.DOMAIN,
            {dynalite.DOMAIN: {dynalite.CONF_BRIDGES: [{dynalite.CONF_HOST: host}]}},
        )
    await hass.async_block_till_done()
    # Find the bridge
    entry_id = await get_entry_id_from_hass(hass)
    bridge = hass.data[dynalite.DOMAIN][entry_id]
    bridge.dynalite_devices.newDeviceFunc([device])
    await hass.async_block_till_done()


async def run_service_tests(hass, device, platform, services):
    """Run a series of service calls and check that the entity and device behave correctly."""
    for cur_item in services:
        service = cur_item[ATTR_SERVICE]
        args = cur_item.get(ATTR_ARGS, {})
        service_data = {"entity_id": f"{platform}.name", **args}
        await hass.services.async_call(platform, service, service_data, blocking=True)
        await hass.async_block_till_done()
        for check_item in services:
            check_method = getattr(device, check_item[ATTR_METHOD])
            if check_item[ATTR_SERVICE] == service:
                check_method.assert_called_once()
                assert check_method.mock_calls == [call(**args)]
                check_method.reset_mock()
            else:
                check_method.assert_not_called()
