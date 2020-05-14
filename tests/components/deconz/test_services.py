"""deCONZ service tests."""

from asynctest import Mock, patch
import pytest
import voluptuous as vol

from homeassistant.components import deconz
from homeassistant.components.deconz.const import CONF_BRIDGE_ID

from .test_gateway import BRIDGEID, setup_deconz_integration

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
    await setup_deconz_integration(hass)

    data = {
        deconz.services.SERVICE_FIELD: "/light/2",
        CONF_BRIDGE_ID: BRIDGEID,
        deconz.services.SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }

    with patch("pydeconz.DeconzSession.request", return_value=Mock(True)) as put_state:
        await hass.services.async_call(
            deconz.DOMAIN, deconz.services.SERVICE_CONFIGURE_DEVICE, service_data=data
        )
        await hass.async_block_till_done()
        put_state.assert_called_with(
            "put", "/light/2", json={"on": True, "attr1": 10, "attr2": 20}
        )


async def test_configure_service_with_entity(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    gateway = await setup_deconz_integration(hass)

    gateway.deconz_ids["light.test"] = "/light/1"
    data = {
        deconz.services.SERVICE_ENTITY: "light.test",
        deconz.services.SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }

    with patch("pydeconz.DeconzSession.request", return_value=Mock(True)) as put_state:
        await hass.services.async_call(
            deconz.DOMAIN, deconz.services.SERVICE_CONFIGURE_DEVICE, service_data=data
        )
        await hass.async_block_till_done()
        put_state.assert_called_with(
            "put", "/light/1", json={"on": True, "attr1": 10, "attr2": 20}
        )


async def test_configure_service_with_entity_and_field(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    gateway = await setup_deconz_integration(hass)

    gateway.deconz_ids["light.test"] = "/light/1"
    data = {
        deconz.services.SERVICE_ENTITY: "light.test",
        deconz.services.SERVICE_FIELD: "/state",
        deconz.services.SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }

    with patch("pydeconz.DeconzSession.request", return_value=Mock(True)) as put_state:
        await hass.services.async_call(
            deconz.DOMAIN, deconz.services.SERVICE_CONFIGURE_DEVICE, service_data=data
        )
        await hass.async_block_till_done()
        put_state.assert_called_with(
            "put", "/light/1/state", json={"on": True, "attr1": 10, "attr2": 20}
        )


async def test_configure_service_with_faulty_field(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    await setup_deconz_integration(hass)

    data = {deconz.services.SERVICE_FIELD: "light/2", deconz.services.SERVICE_DATA: {}}

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            deconz.DOMAIN, deconz.services.SERVICE_CONFIGURE_DEVICE, service_data=data
        )
        await hass.async_block_till_done()


async def test_configure_service_with_faulty_entity(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    await setup_deconz_integration(hass)

    data = {
        deconz.services.SERVICE_ENTITY: "light.nonexisting",
        deconz.services.SERVICE_DATA: {},
    }

    with patch("pydeconz.DeconzSession.request", return_value=Mock(True)) as put_state:
        await hass.services.async_call(
            deconz.DOMAIN, deconz.services.SERVICE_CONFIGURE_DEVICE, service_data=data
        )
        await hass.async_block_till_done()
        put_state.assert_not_called()


async def test_service_refresh_devices(hass):
    """Test that service can refresh devices."""
    gateway = await setup_deconz_integration(hass)

    data = {CONF_BRIDGE_ID: BRIDGEID}

    with patch(
        "pydeconz.DeconzSession.request",
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
