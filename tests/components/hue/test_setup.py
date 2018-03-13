"""Test Hue setup process."""
from homeassistant.setup import async_setup_component
from homeassistant.components import hue
from homeassistant.components.discovery import SERVICE_HUE


async def test_setup_with_multiple_hosts(hass, mock_bridge):
    """Multiple hosts specified in the config file."""
    assert await async_setup_component(hass, hue.DOMAIN, {
        hue.DOMAIN: {
            hue.CONF_BRIDGES: [
                {hue.CONF_HOST: '127.0.0.1'},
                {hue.CONF_HOST: '192.168.1.10'},
            ]
        }
    })

    assert len(mock_bridge.mock_calls) == 2
    hosts = sorted(mock_call[1][0] for mock_call in mock_bridge.mock_calls)
    assert hosts == ['127.0.0.1', '192.168.1.10']
    assert len(hass.data[hue.DOMAIN]) == 2


async def test_bridge_discovered(hass, mock_bridge):
    """Bridge discovery."""
    assert await async_setup_component(hass, hue.DOMAIN, {})

    await hass.helpers.discovery.async_discover(SERVICE_HUE, {
        'host': '192.168.1.10',
        'serial': '1234567',
    })
    await hass.async_block_till_done()

    assert len(mock_bridge.mock_calls) == 1
    assert mock_bridge.mock_calls[0][1][0] == '192.168.1.10'
    assert len(hass.data[hue.DOMAIN]) == 1


async def test_bridge_configure_and_discovered(hass, mock_bridge):
    """Bridge is in the config file, then we discover it."""
    assert await async_setup_component(hass, hue.DOMAIN, {
        hue.DOMAIN: {
            hue.CONF_BRIDGES: {
                hue.CONF_HOST: '192.168.1.10'
            }
        }
    })

    assert len(mock_bridge.mock_calls) == 1
    assert mock_bridge.mock_calls[0][1][0] == '192.168.1.10'
    assert len(hass.data[hue.DOMAIN]) == 1

    mock_bridge.reset_mock()

    await hass.helpers.discovery.async_discover(SERVICE_HUE, {
        'host': '192.168.1.10',
        'serial': '1234567',
    })
    await hass.async_block_till_done()

    assert len(mock_bridge.mock_calls) == 0
    assert len(hass.data[hue.DOMAIN]) == 1


async def test_setup_no_host(hass, aioclient_mock):
    """Check we call discovery if domain specified but no bridges."""
    aioclient_mock.get(hue.API_NUPNP, json=[])

    result = await async_setup_component(
        hass, hue.DOMAIN, {hue.DOMAIN: {}})
    assert result

    assert len(aioclient_mock.mock_calls) == 1
    assert len(hass.data[hue.DOMAIN]) == 0
