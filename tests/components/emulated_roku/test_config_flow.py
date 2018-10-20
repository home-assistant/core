"""Tests for emulated_roku config flow."""
from homeassistant.components.emulated_roku import config_flow
from tests.common import MockConfigEntry


async def test_flow_works(hass):
    """Test that config flow works."""
    flow = config_flow.EmulatedRokuFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input={
        'name': 'Emulated Roku Test',
        'listen_port': 8060,
        'host_ip': '1.2.3.4',
        'advertise_ip': '1.2.3.5',
        'advertise_port': 8070,
        'upnp_bind_multicast': False
    })

    assert result['type'] == 'create_entry'
    assert result['title'] == 'Emulated Roku Test'
    assert result['data'] == {
        'name': 'Emulated Roku Test',
        'listen_port': 8060,
        'host_ip': '1.2.3.4',
        'advertise_ip': '1.2.3.5',
        'advertise_port': 8070,
        'upnp_bind_multicast': False
    }


async def test_flow_already_registered_entry(hass):
    """Test config flow don't allow more than one bridge to be registered."""
    MockConfigEntry(domain='emulated_roku', data={
        'name': 'Emulated Roku Test',
        'listen_port': 8062
    }).add_to_hass(hass)
    flow = config_flow.EmulatedRokuFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input={
        'name': 'Emulated Roku Test',
        'listen_port': 8062
    })
    assert result['type'] == 'abort'
