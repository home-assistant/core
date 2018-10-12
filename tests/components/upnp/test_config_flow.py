"""Tests for UPnP/IGD config flow."""

from homeassistant.components import upnp
from homeassistant.components.upnp import config_flow as upnp_config_flow

from tests.common import MockConfigEntry


async def test_flow_none_discovered(hass):
    """Test no device discovered flow."""
    flow = upnp_config_flow.UpnpFlowHandler()
    flow.hass = hass
    hass.data[upnp.DOMAIN] = {
        'discovered': {}
    }

    result = await flow.async_step_user()
    assert result['type'] == 'abort'
    assert result['reason'] == 'no_devices_discovered'


async def test_flow_already_configured(hass):
    """Test device already configured flow."""
    flow = upnp_config_flow.UpnpFlowHandler()
    flow.hass = hass

    # discovered device
    udn = 'uuid:device_1'
    hass.data[upnp.DOMAIN] = {
        'discovered': {
            udn: {
                'friendly_name': '192.168.1.1 (Test device)',
                'host': '192.168.1.1',
                'udn': udn,
            },
        },
    }

    # configured entry
    MockConfigEntry(domain=upnp.DOMAIN, data={
        'udn': udn,
        'host': '192.168.1.1',
    }).add_to_hass(hass)

    result = await flow.async_step_user({
        'name': '192.168.1.1 (Test device)',
        'enable_sensors': True,
        'enable_port_mapping': False,
    })
    assert result['type'] == 'abort'
    assert result['reason'] == 'already_configured'


async def test_flow_no_sensors_no_port_mapping(hass):
    """Test single device, no sensors, no port_mapping."""
    flow = upnp_config_flow.UpnpFlowHandler()
    flow.hass = hass

    # discovered device
    udn = 'uuid:device_1'
    hass.data[upnp.DOMAIN] = {
        'discovered': {
            udn: {
                'friendly_name': '192.168.1.1 (Test device)',
                'host': '192.168.1.1',
                'udn': udn,
            },
        },
    }

    # configured entry
    MockConfigEntry(domain=upnp.DOMAIN, data={
        'udn': udn,
        'host': '192.168.1.1',
    }).add_to_hass(hass)

    result = await flow.async_step_user({
        'name': '192.168.1.1 (Test device)',
        'enable_sensors': False,
        'enable_port_mapping': False,
    })
    assert result['type'] == 'abort'
    assert result['reason'] == 'no_sensors_or_port_mapping'


async def test_flow_discovered_form(hass):
    """Test single device discovered, show form flow."""
    flow = upnp_config_flow.UpnpFlowHandler()
    flow.hass = hass

    # discovered device
    udn = 'uuid:device_1'
    hass.data[upnp.DOMAIN] = {
        'discovered': {
            udn: {
                'friendly_name': '192.168.1.1 (Test device)',
                'host': '192.168.1.1',
                'udn': udn,
            },
        },
    }

    result = await flow.async_step_user()
    assert result['type'] == 'form'
    assert result['step_id'] == 'user'


async def test_flow_two_discovered_form(hass):
    """Test two devices discovered, show form flow with two devices."""
    flow = upnp_config_flow.UpnpFlowHandler()
    flow.hass = hass

    # discovered device
    udn_1 = 'uuid:device_1'
    udn_2 = 'uuid:device_2'
    hass.data[upnp.DOMAIN] = {
        'discovered': {
            udn_1: {
                'friendly_name': '192.168.1.1 (Test device)',
                'host': '192.168.1.1',
                'udn': udn_1,
            },
            udn_2: {
                'friendly_name': '192.168.2.1 (Test device)',
                'host': '192.168.2.1',
                'udn': udn_2,
            },
        },
    }

    result = await flow.async_step_user()
    assert result['type'] == 'form'
    assert result['step_id'] == 'user'
    assert result['data_schema']({
        'name': '192.168.1.1 (Test device)',
        'enable_sensors': True,
        'enable_port_mapping': False,
    })
    assert result['data_schema']({
        'name': '192.168.2.1 (Test device)',
        'enable_sensors': True,
        'enable_port_mapping': False,
    })


async def test_config_entry_created(hass):
    """Test config entry is created."""
    flow = upnp_config_flow.UpnpFlowHandler()
    flow.hass = hass

    # discovered device
    hass.data[upnp.DOMAIN] = {
        'discovered': {
            'uuid:device_1': {
                'friendly_name': '192.168.1.1 (Test device)',
                'name': 'Test device 1',
                'host': '192.168.1.1',
                'ssdp_description': 'http://192.168.1.1/desc.xml',
                'udn': 'uuid:device_1',
            },
        },
    }

    result = await flow.async_step_user({
        'name': '192.168.1.1 (Test device)',
        'enable_sensors': True,
        'enable_port_mapping': False,
    })
    assert result['type'] == 'create_entry'
    assert result['data'] == {
        'ssdp_description': 'http://192.168.1.1/desc.xml',
        'udn': 'uuid:device_1',
        'port_mapping': False,
        'sensors': True,
    }
    assert result['title'] == 'Test device 1'


async def test_flow_discovery_auto_config_sensors(hass):
    """Test creation of device with auto_config."""
    flow = upnp_config_flow.UpnpFlowHandler()
    flow.hass = hass

    # auto_config active
    hass.data[upnp.DOMAIN] = {
        'auto_config': {
            'active': True,
            'enable_port_mapping': False,
            'enable_sensors': True,
        },
    }

    # discovered device
    result = await flow.async_step_discovery({
        'name': 'Test device 1',
        'host': '192.168.1.1',
        'ssdp_description': 'http://192.168.1.1/desc.xml',
        'udn': 'uuid:device_1',
    })

    assert result['type'] == 'create_entry'
    assert result['data'] == {
        'ssdp_description': 'http://192.168.1.1/desc.xml',
        'udn': 'uuid:device_1',
        'sensors': True,
        'port_mapping': False,
    }
    assert result['title'] == 'Test device 1'


async def test_flow_discovery_auto_config_sensors_port_mapping(hass):
    """Test creation of device with auto_config, with port mapping."""
    flow = upnp_config_flow.UpnpFlowHandler()
    flow.hass = hass

    # auto_config active, with port_mapping
    hass.data[upnp.DOMAIN] = {
        'auto_config': {
            'active': True,
            'enable_port_mapping': True,
            'enable_sensors': True,
        },
    }

    # discovered device
    result = await flow.async_step_discovery({
        'name': 'Test device 1',
        'host': '192.168.1.1',
        'ssdp_description': 'http://192.168.1.1/desc.xml',
        'udn': 'uuid:device_1',
    })

    assert result['type'] == 'create_entry'
    assert result['data'] == {
        'udn': 'uuid:device_1',
        'ssdp_description': 'http://192.168.1.1/desc.xml',
        'sensors': True,
        'port_mapping': True,
    }
    assert result['title'] == 'Test device 1'
