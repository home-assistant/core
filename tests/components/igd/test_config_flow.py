"""Tests for IGD config flow."""

from homeassistant.components import igd

from tests.common import MockConfigEntry


async def test_flow_none_discovered(hass):
    """Test no device discovered flow."""
    flow = igd.config_flow.IgdFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result['type'] == 'abort'
    assert result['reason'] == 'no_devices_discovered'


async def test_flow_already_configured(hass):
    """Test device already configured flow."""
    flow = igd.config_flow.IgdFlowHandler()
    flow.hass = hass

    # discovered device
    udn = 'uuid:device_1'
    hass.data[igd.DOMAIN] = {
        'discovered': {
            udn: {
                'host': '192.168.1.1',
                'udn': udn,
            },
        },
    }

    # configured entry
    MockConfigEntry(domain=igd.DOMAIN, data={
        'udn': udn,
        'host': '192.168.1.1',
    }).add_to_hass(hass)

    result = await flow.async_step_user({
        'igd_host': '192.168.1.1',
        'sensors': True,
        'port_forward': False,
    })
    assert result['type'] == 'abort'
    assert result['reason'] == 'already_configured'


async def test_flow_no_sensors_no_port_forward(hass):
    """Test single device, no sensors, no port_forward."""
    flow = igd.config_flow.IgdFlowHandler()
    flow.hass = hass

    # discovered device
    udn = 'uuid:device_1'
    hass.data[igd.DOMAIN] = {
        'discovered': {
            udn: {
                'host': '192.168.1.1',
                'udn': udn,
            },
        },
    }

    # configured entry
    MockConfigEntry(domain=igd.DOMAIN, data={
        'udn': udn,
        'host': '192.168.1.1',
    }).add_to_hass(hass)

    result = await flow.async_step_user({
        'igd_host': '192.168.1.1',
        'sensors': False,
        'port_forward': False,
    })
    assert result['type'] == 'abort'
    assert result['reason'] == 'no_sensors_or_port_forward'


async def test_flow_discovered_form(hass):
    """Test single device discovered, show form flow."""
    flow = igd.config_flow.IgdFlowHandler()
    flow.hass = hass

    # discovered device
    udn = 'uuid:device_1'
    hass.data[igd.DOMAIN] = {
        'discovered': {
            udn: {
                'host': '192.168.1.1',
                'udn': udn,
            },
        },
    }

    result = await flow.async_step_user()
    assert result['type'] == 'form'
    assert result['step_id'] == 'user'


async def test_flow_two_discovered_form(hass):
    """Test single device discovered, show form flow."""
    flow = igd.config_flow.IgdFlowHandler()
    flow.hass = hass

    # discovered device
    udn_1 = 'uuid:device_1'
    udn_2 = 'uuid:device_2'
    hass.data[igd.DOMAIN] = {
        'discovered': {
            udn_1: {
                'host': '192.168.1.1',
                'udn': udn_1,
            },
            udn_2: {
                'host': '192.168.2.1',
                'udn': udn_2,
            },
        },
    }

    result = await flow.async_step_user()
    assert result['type'] == 'form'
    assert result['step_id'] == 'user'
    assert result['data_schema']({
        'igd_host': '192.168.1.1',
        'sensors': True,
        'port_forward': False,
    })
    assert result['data_schema']({
        'igd_host': '192.168.2.1',
        'sensors': True,
        'port_forward': False,
    })


async def test_config_entry_created(hass):
    flow = igd.config_flow.IgdFlowHandler()
    flow.hass = hass

    # discovered device
    udn = 'uuid:device_1'
    hass.data[igd.DOMAIN] = {
        'discovered': {
            udn: {
                'name': 'Test device 1',
                'host': '192.168.1.1',
                'ssdp_description': 'http://192.168.1.1/desc.xml',
                'udn': udn,
            },
        },
    }

    result = await flow.async_step_user({
        'igd_host': '192.168.1.1',
        'sensors': True,
        'port_forward': False,
    })
    assert result['data'] == {
        'port_forward': False,
        'sensors': True,
        'ssdp_description': 'http://192.168.1.1/desc.xml',
        'udn': 'uuid:device_1',
    }
    assert result['title'] == 'Test device 1'
