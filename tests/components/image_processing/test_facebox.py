"""The tests for the facebox component."""
import requests_mock

from homeassistant.const import (CONF_IP_ADDRESS, CONF_PORT)
from homeassistant.setup import async_setup_component
import homeassistant.components.image_processing as ip

MOCK_IP = '192.168.0.1'
MOCK_PORT = '8080'

MOCK_RESPONSE = """
{"facesCount": 1,
"success": True,
"faces":[{'confidence': 0.5812028911604818,
            'id': 'john.jpg',
            'matched': True,
            'name': 'John Lennon',
            'rect': {'height': 75, 'left': 63, 'top': 262, 'width': 74}
            }]
"""

VALID_ENTITY_ID = 'image_processing.facebox_demo_camera'
VALID_CONFIG = {
    ip.DOMAIN: {
        'platform': 'facebox',
        CONF_IP_ADDRESS: MOCK_IP,
        CONF_PORT: MOCK_PORT,
        ip.CONF_SOURCE: {
            ip.CONF_ENTITY_ID: 'camera.demo_camera'}
        },
    'camera': {
        'platform': 'demo'
        }
    }


async def test_setup_platform(hass):
    """Setup platform with one entity."""

    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)


async def test_process_image(hass):
    """Test processing of an image."""

    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)

    with requests_mock.Mocker() as mock_req:
        url = "http://{}:{}/facebox/check".format(MOCK_IP, MOCK_PORT)
        mock_req.post(url, text=MOCK_RESPONSE)
        await hass.services.async_call(ip.DOMAIN,
                                       'scan',
                                       {'entity_id': VALID_ENTITY_ID})
        await hass.async_block_till_done()

    state = hass.states.get(VALID_ENTITY_ID)
    assert state.state == '1'
