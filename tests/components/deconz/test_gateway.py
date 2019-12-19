"""Test deCONZ gateway."""
from copy import deepcopy

from asynctest import Mock, patch
import pydeconz
import pytest

from homeassistant import config_entries
from homeassistant.components import deconz, ssdp
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect

BRIDGEID = "0123456789"

ENTRY_CONFIG = {
    deconz.config_flow.CONF_API_KEY: "ABCDEF",
    deconz.config_flow.CONF_BRIDGEID: BRIDGEID,
    deconz.config_flow.CONF_HOST: "1.2.3.4",
    deconz.config_flow.CONF_PORT: 80,
    deconz.config_flow.CONF_UUID: "456DEF",
}

DECONZ_CONFIG = {
    "bridgeid": BRIDGEID,
    "ipaddress": "1.2.3.4",
    "mac": "00:11:22:33:44:55",
    "modelid": "deCONZ",
    "name": "deCONZ mock gateway",
    "sw_version": "2.05.69",
    "uuid": "1234",
    "websocketport": 1234,
}

DECONZ_WEB_REQUEST = {"config": DECONZ_CONFIG}


async def setup_deconz_integration(hass, config, options, get_state_response):
    """Create the deCONZ gateway."""
    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=deconz.DOMAIN,
        title="Mock Title",
        data=config,
        source="test",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        system_options={},
        options=options,
        entry_id="1",
    )

    for resource in ("groups", "lights", "sensors"):
        if resource not in get_state_response:
            get_state_response[resource] = {}

    with patch(
        "pydeconz.DeconzSession.request", return_value=get_state_response
    ), patch("pydeconz.DeconzSession.start", return_value=True):
        await deconz.async_setup_entry(hass, config_entry)
    await hass.async_block_till_done()

    hass.config_entries._entries.append(config_entry)

    return hass.data[deconz.DOMAIN].get(config[deconz.CONF_BRIDGEID])


async def test_gateway_setup(hass):
    """Successful setup."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        gateway = await setup_deconz_integration(
            hass, ENTRY_CONFIG, options={}, get_state_response=data
        )
        assert gateway.bridgeid == BRIDGEID
        assert gateway.master is True
        assert gateway.option_allow_clip_sensor is False
        assert gateway.option_allow_deconz_groups is True

        assert len(gateway.deconz_ids) == 0
        assert len(hass.states.async_all()) == 0

        entry = gateway.config_entry
        assert forward_entry_setup.mock_calls[0][1] == (entry, "binary_sensor")
        assert forward_entry_setup.mock_calls[1][1] == (entry, "climate")
        assert forward_entry_setup.mock_calls[2][1] == (entry, "cover")
        assert forward_entry_setup.mock_calls[3][1] == (entry, "light")
        assert forward_entry_setup.mock_calls[4][1] == (entry, "scene")
        assert forward_entry_setup.mock_calls[5][1] == (entry, "sensor")
        assert forward_entry_setup.mock_calls[6][1] == (entry, "switch")


async def test_gateway_retry(hass):
    """Retry setup."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    with patch(
        "homeassistant.components.deconz.gateway.get_gateway",
        side_effect=deconz.errors.CannotConnect,
    ), pytest.raises(ConfigEntryNotReady):
        await setup_deconz_integration(
            hass, ENTRY_CONFIG, options={}, get_state_response=data
        )


async def test_gateway_setup_fails(hass):
    """Retry setup."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    with patch(
        "homeassistant.components.deconz.gateway.get_gateway", side_effect=Exception
    ):
        gateway = await setup_deconz_integration(
            hass, ENTRY_CONFIG, options={}, get_state_response=data
        )
        assert gateway is None


async def test_connection_status_signalling(hass):
    """Make sure that connection status triggers a dispatcher send."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    gateway = await setup_deconz_integration(
        hass, ENTRY_CONFIG, options={}, get_state_response=data
    )

    event_call = Mock()
    unsub = async_dispatcher_connect(hass, gateway.signal_reachable, event_call)

    gateway.async_connection_status_callback(False)
    await hass.async_block_till_done()

    assert gateway.available is False
    assert len(event_call.mock_calls) == 1

    unsub()


async def test_update_address(hass):
    """Make sure that connection status triggers a dispatcher send."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    gateway = await setup_deconz_integration(
        hass, ENTRY_CONFIG, options={}, get_state_response=data
    )
    assert gateway.api.host == "1.2.3.4"

    await hass.config_entries.flow.async_init(
        deconz.config_flow.DOMAIN,
        data={
            ssdp.ATTR_SSDP_LOCATION: "http://2.3.4.5:80/",
            ssdp.ATTR_UPNP_MANUFACTURER_URL: deconz.config_flow.DECONZ_MANUFACTURERURL,
            ssdp.ATTR_UPNP_SERIAL: BRIDGEID,
            ssdp.ATTR_UPNP_UDN: "uuid:456DEF",
        },
        context={"source": "ssdp"},
    )
    await hass.async_block_till_done()

    assert gateway.api.host == "2.3.4.5"


async def test_reset_after_successful_setup(hass):
    """Make sure that connection status triggers a dispatcher send."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    gateway = await setup_deconz_integration(
        hass, ENTRY_CONFIG, options={}, get_state_response=data
    )

    result = await gateway.async_reset()
    await hass.async_block_till_done()

    assert result is True


async def test_get_gateway(hass):
    """Successful call."""
    with patch("pydeconz.DeconzSession.initialize", return_value=True):
        assert await deconz.gateway.get_gateway(hass, ENTRY_CONFIG, Mock(), Mock())


async def test_get_gateway_fails_unauthorized(hass):
    """Failed call."""
    with patch(
        "pydeconz.DeconzSession.initialize", side_effect=pydeconz.errors.Unauthorized,
    ), pytest.raises(deconz.errors.AuthenticationRequired):
        assert (
            await deconz.gateway.get_gateway(hass, ENTRY_CONFIG, Mock(), Mock())
            is False
        )


async def test_get_gateway_fails_cannot_connect(hass):
    """Failed call."""
    with patch(
        "pydeconz.DeconzSession.initialize", side_effect=pydeconz.errors.RequestError,
    ), pytest.raises(deconz.errors.CannotConnect):
        assert (
            await deconz.gateway.get_gateway(hass, ENTRY_CONFIG, Mock(), Mock())
            is False
        )
