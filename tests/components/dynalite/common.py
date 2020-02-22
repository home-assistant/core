"""Common functions for tests."""
from asynctest import Mock, call, patch

from homeassistant.components import dynalite
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


def get_bridge_from_hass(hass_obj):
    """Get the bridge from hass.data."""
    key = next(iter(hass_obj.data[dynalite.DOMAIN]))
    return hass_obj.data[dynalite.DOMAIN][key]


async def create_entity_from_device(hass, device):
    """Set up the component and platform and create a light based on the device provided."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.available", True
    ):
        assert await async_setup_component(
            hass,
            dynalite.DOMAIN,
            {dynalite.DOMAIN: {dynalite.CONF_BRIDGES: [{dynalite.CONF_HOST: host}]}},
        )
    await hass.async_block_till_done()
    # Find the bridge
    bridge = None
    assert len(hass.data[dynalite.DOMAIN]) == 1
    bridge = get_bridge_from_hass(hass)
    bridge.dynalite_devices.newDeviceFunc([device])
    await hass.async_block_till_done()


async def run_service_tests(hass_obj, device, platform, services):
    """Run a series of service calls and check that the entity and device behave correctly."""
    for cur_item in services:
        service = cur_item[ATTR_SERVICE]
        args = cur_item.get(ATTR_ARGS, {})
        service_data = {"entity_id": f"{platform}.name", **args}
        await hass_obj.services.async_call(
            platform, service, service_data, blocking=True
        )
        await hass_obj.async_block_till_done()
        for check_item in services:
            check_method = getattr(device, check_item[ATTR_METHOD])
            if check_item[ATTR_SERVICE] == service:
                check_method.assert_called_once()
                assert check_method.mock_calls == [call(**args)]
                check_method.reset_mock()
            else:
                check_method.assert_not_called()
