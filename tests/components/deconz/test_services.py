"""deCONZ service tests."""
from asynctest import Mock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import deconz

BRIDGEID = "0123456789"

ENTRY_CONFIG = {
    deconz.config_flow.CONF_API_KEY: "ABCDEF",
    deconz.config_flow.CONF_BRIDGEID: BRIDGEID,
    deconz.config_flow.CONF_HOST: "1.2.3.4",
    deconz.config_flow.CONF_PORT: 80,
}

DECONZ_CONFIG = {
    "bridgeid": BRIDGEID,
    "mac": "00:11:22:33:44:55",
    "name": "deCONZ mock gateway",
    "sw_version": "2.05.69",
    "websocketport": 1234,
}

DECONZ_WEB_REQUEST = {"config": DECONZ_CONFIG}

GROUP = {
    "1": {
        "id": "Group 1 id",
        "name": "Group 1 name",
        "type": "LightGroup",
        "state": {},
        "action": {},
        "scenes": [{"id": "1", "name": "Scene 1"}],
        "lights": ["1"],
    }
}

LIGHT = {
    "1": {
        "id": "Light 1 id",
        "name": "Light 1 name",
        "state": {"reachable": True},
        "type": "Light",
        "uniqueid": "00:00:00:00:00:00:00:01-00",
    }
}

SENSOR = {
    "1": {
        "id": "Sensor 1 id",
        "name": "Sensor 1 name",
        "type": "ZHALightLevel",
        "state": {"lightlevel": 30000, "dark": False},
        "config": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:02-00",
    }
}


async def setup_deconz_integration(hass, options):
    """Create the deCONZ gateway."""
    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=deconz.DOMAIN,
        title="Mock Title",
        data=ENTRY_CONFIG,
        source="test",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        system_options={},
        options=options,
        entry_id="1",
    )

    with patch(
        "pydeconz.DeconzSession.async_get_state", return_value=DECONZ_WEB_REQUEST
    ):
        await deconz.async_setup_entry(hass, config_entry)
    await hass.async_block_till_done()

    hass.config_entries._entries.append(config_entry)

    return hass.data[deconz.DOMAIN][BRIDGEID]


async def test_service_setup(hass):
    """Verify service setup works."""
    assert deconz.services.DECONZ_SERVICES not in hass.data
    with patch(
        "homeassistant.core.ServiceRegistry.async_register", return_value=Mock(True)
    ) as async_register:
        await deconz.services.async_setup_services(hass)
        assert hass.data[deconz.services.DECONZ_SERVICES] is True
        assert async_register.call_count == 2


async def test_service_setup_already_registered(hass):
    """Make sure that services are only registered once."""
    hass.data[deconz.services.DECONZ_SERVICES] = True
    with patch(
        "homeassistant.core.ServiceRegistry.async_register", return_value=Mock(True)
    ) as async_register:
        await deconz.services.async_setup_services(hass)
        async_register.assert_not_called()


async def test_service_unload(hass):
    """Verify service unload works."""
    hass.data[deconz.services.DECONZ_SERVICES] = True
    with patch(
        "homeassistant.core.ServiceRegistry.async_remove", return_value=Mock(True)
    ) as async_remove:
        await deconz.services.async_unload_services(hass)
        assert hass.data[deconz.services.DECONZ_SERVICES] is False
        assert async_remove.call_count == 2


async def test_service_unload_not_registered(hass):
    """Make sure that services can only be unloaded once."""
    with patch(
        "homeassistant.core.ServiceRegistry.async_remove", return_value=Mock(True)
    ) as async_remove:
        await deconz.services.async_unload_services(hass)
        assert deconz.services.DECONZ_SERVICES not in hass.data
        async_remove.assert_not_called()


async def test_configure_service_with_field(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    await setup_deconz_integration(hass, options={})

    data = {
        deconz.services.SERVICE_FIELD: "/light/2",
        deconz.CONF_BRIDGEID: BRIDGEID,
        deconz.services.SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }

    with patch(
        "pydeconz.DeconzSession.async_put_state", return_value=Mock(True)
    ) as put_state:
        await hass.services.async_call(
            deconz.DOMAIN, deconz.services.SERVICE_CONFIGURE_DEVICE, service_data=data
        )
        await hass.async_block_till_done()
        put_state.assert_called_with("/light/2", {"on": True, "attr1": 10, "attr2": 20})


async def test_configure_service_with_entity(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    gateway = await setup_deconz_integration(hass, options={})

    gateway.deconz_ids["light.test"] = "/light/1"
    data = {
        deconz.services.SERVICE_ENTITY: "light.test",
        deconz.services.SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }

    with patch(
        "pydeconz.DeconzSession.async_put_state", return_value=Mock(True)
    ) as put_state:
        await hass.services.async_call(
            deconz.DOMAIN, deconz.services.SERVICE_CONFIGURE_DEVICE, service_data=data
        )
        await hass.async_block_till_done()
        put_state.assert_called_with("/light/1", {"on": True, "attr1": 10, "attr2": 20})


async def test_configure_service_with_entity_and_field(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    gateway = await setup_deconz_integration(hass, options={})

    gateway.deconz_ids["light.test"] = "/light/1"
    data = {
        deconz.services.SERVICE_ENTITY: "light.test",
        deconz.services.SERVICE_FIELD: "/state",
        deconz.services.SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }

    with patch(
        "pydeconz.DeconzSession.async_put_state", return_value=Mock(True)
    ) as put_state:
        await hass.services.async_call(
            deconz.DOMAIN, deconz.services.SERVICE_CONFIGURE_DEVICE, service_data=data
        )
        await hass.async_block_till_done()
        put_state.assert_called_with(
            "/light/1/state", {"on": True, "attr1": 10, "attr2": 20}
        )


async def test_configure_service_with_faulty_field(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    await setup_deconz_integration(hass, options={})

    data = {deconz.services.SERVICE_FIELD: "light/2", deconz.services.SERVICE_DATA: {}}

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            deconz.DOMAIN, deconz.services.SERVICE_CONFIGURE_DEVICE, service_data=data
        )
        await hass.async_block_till_done()


async def test_configure_service_with_faulty_entity(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    await setup_deconz_integration(hass, options={})

    data = {
        deconz.services.SERVICE_ENTITY: "light.nonexisting",
        deconz.services.SERVICE_DATA: {},
    }

    with patch(
        "pydeconz.DeconzSession.async_put_state", return_value=Mock(True)
    ) as put_state:
        await hass.services.async_call(
            deconz.DOMAIN, deconz.services.SERVICE_CONFIGURE_DEVICE, service_data=data
        )
        await hass.async_block_till_done()
        put_state.assert_not_called()


async def test_service_refresh_devices(hass):
    """Test that service can refresh devices."""
    gateway = await setup_deconz_integration(hass, options={})

    data = {deconz.CONF_BRIDGEID: BRIDGEID}

    with patch(
        "pydeconz.DeconzSession.async_get_state",
        return_value={"groups": GROUP, "lights": LIGHT, "sensors": SENSOR},
    ):
        await hass.services.async_call(
            deconz.DOMAIN, deconz.services.SERVICE_DEVICE_REFRESH, service_data=data
        )
        await hass.async_block_till_done()

    assert gateway.deconz_ids == {
        "light.group_1_name": "/groups/1",
        "light.light_1_name": "/lights/1",
        "scene.group_1_name_scene_1": "/groups/1/scenes/1",
        "sensor.sensor_1_name": "/sensors/1",
    }
