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


async def test_configure_service_with_field(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    await setup_deconz_integration(hass, options={})

    data = {"on": True, "attr1": 10, "attr2": 20, deconz.CONF_BRIDGEID: BRIDGEID}

    with patch(
        "pydeconz.DeconzSession.async_put_state", return_value=Mock(True)
    ) as put_state:
        await hass.services.async_call(
            "deconz", "configure", service_data={"field": "/light/2", "data": data}
        )
        await hass.async_block_till_done()
        put_state.assert_called_with("/light/2", {"on": True, "attr1": 10, "attr2": 20})


async def test_configure_service_with_entity(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    gateway = await setup_deconz_integration(hass, options={})

    gateway.deconz_ids["light.test"] = "/light/1"
    data = {"on": True, "attr1": 10, "attr2": 20}

    with patch(
        "pydeconz.DeconzSession.async_put_state", return_value=Mock(True)
    ) as put_state:
        await hass.services.async_call(
            "deconz", "configure", service_data={"entity": "light.test", "data": data}
        )
        await hass.async_block_till_done()
        put_state.assert_called_with("/light/1", {"on": True, "attr1": 10, "attr2": 20})


async def test_configure_service_with_entity_and_field(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    gateway = await setup_deconz_integration(hass, options={})

    gateway.deconz_ids["light.test"] = "/light/1"
    data = {"on": True, "attr1": 10, "attr2": 20}

    with patch(
        "pydeconz.DeconzSession.async_put_state", return_value=Mock(True)
    ) as put_state:
        await hass.services.async_call(
            "deconz",
            "configure",
            service_data={"entity": "light.test", "field": "/state", "data": data},
        )
        await hass.async_block_till_done()
        put_state.assert_called_with(
            "/light/1/state", {"on": True, "attr1": 10, "attr2": 20}
        )


async def test_configure_service_with_faulty_field(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    await setup_deconz_integration(hass, options={})

    data = {}

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "deconz", "configure", service_data={"field": "light/2", "data": data}
        )
        await hass.async_block_till_done()


async def test_configure_service_with_faulty_entity(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    await setup_deconz_integration(hass, options={})

    data = {}

    with patch(
        "pydeconz.DeconzSession.async_put_state", return_value=Mock(True)
    ) as put_state:
        await hass.services.async_call(
            "deconz",
            "configure",
            service_data={"entity": "light.nonexisting", "data": data},
        )
        await hass.async_block_till_done()
        put_state.assert_not_called()
