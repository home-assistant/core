"""Test Hue setup process."""
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.components import hue

from tests.common import mock_coro, MockConfigEntry


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to setup a bridge."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(hue, 'configured_hosts', return_value=[]):
        assert await async_setup_component(hass, hue.DOMAIN, {}) is True

    # No flows started
    assert len(mock_config_entries.flow.mock_calls) == 0

    # No configs stored
    assert hass.data[hue.DOMAIN] == {}


async def test_setup_with_discovery_no_known_auth(hass, aioclient_mock):
    """Test discovering a bridge and not having known auth."""
    aioclient_mock.get(hue.API_NUPNP, json=[
        {
            'internalipaddress': '0.0.0.0',
            'id': 'abcd1234'
        }
    ])

    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(hue, 'configured_hosts', return_value=[]):
        mock_config_entries.flow.async_init.return_value = mock_coro()
        assert await async_setup_component(hass, hue.DOMAIN, {
            hue.DOMAIN: {}
        }) is True

    # Flow started for discovered bridge
    assert len(mock_config_entries.flow.mock_calls) == 1
    assert mock_config_entries.flow.mock_calls[0][2]['data'] == {
        'host': '0.0.0.0',
        'path': '.hue_abcd1234.conf',
    }

    # Config stored for domain.
    assert hass.data[hue.DOMAIN] == {
        '0.0.0.0': {
            hue.CONF_HOST: '0.0.0.0',
            hue.CONF_FILENAME: '.hue_abcd1234.conf',
            hue.CONF_ALLOW_HUE_GROUPS: hue.DEFAULT_ALLOW_HUE_GROUPS,
            hue.CONF_ALLOW_UNREACHABLE: hue.DEFAULT_ALLOW_UNREACHABLE,
        }
    }


async def test_setup_with_discovery_known_auth(hass, aioclient_mock):
    """Test we don't do anything if we discover already configured hub."""
    aioclient_mock.get(hue.API_NUPNP, json=[
        {
            'internalipaddress': '0.0.0.0',
            'id': 'abcd1234'
        }
    ])

    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(hue, 'configured_hosts', return_value=['0.0.0.0']):
        assert await async_setup_component(hass, hue.DOMAIN, {
            hue.DOMAIN: {}
        }) is True

    # Flow started for discovered bridge
    assert len(mock_config_entries.flow.mock_calls) == 0

    # Config stored for domain.
    assert hass.data[hue.DOMAIN] == {}


async def test_setup_defined_hosts_known_auth(hass):
    """Test we don't initiate a config entry if config bridge is known."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(hue, 'configured_hosts', return_value=['0.0.0.0']):
        assert await async_setup_component(hass, hue.DOMAIN, {
            hue.DOMAIN: {
                hue.CONF_BRIDGES: {
                    hue.CONF_HOST: '0.0.0.0',
                    hue.CONF_FILENAME: 'bla.conf',
                    hue.CONF_ALLOW_HUE_GROUPS: False,
                    hue.CONF_ALLOW_UNREACHABLE: True
                }
            }
        }) is True

    # Flow started for discovered bridge
    assert len(mock_config_entries.flow.mock_calls) == 0

    # Config stored for domain.
    assert hass.data[hue.DOMAIN] == {
        '0.0.0.0': {
            hue.CONF_HOST: '0.0.0.0',
            hue.CONF_FILENAME: 'bla.conf',
            hue.CONF_ALLOW_HUE_GROUPS: False,
            hue.CONF_ALLOW_UNREACHABLE: True
        }
    }


async def test_setup_defined_hosts_no_known_auth(hass):
    """Test we initiate config entry if config bridge is not known."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(hue, 'configured_hosts', return_value=[]):
        mock_config_entries.flow.async_init.return_value = mock_coro()
        assert await async_setup_component(hass, hue.DOMAIN, {
            hue.DOMAIN: {
                hue.CONF_BRIDGES: {
                    hue.CONF_HOST: '0.0.0.0',
                    hue.CONF_FILENAME: 'bla.conf',
                    hue.CONF_ALLOW_HUE_GROUPS: False,
                    hue.CONF_ALLOW_UNREACHABLE: True
                }
            }
        }) is True

    # Flow started for discovered bridge
    assert len(mock_config_entries.flow.mock_calls) == 1
    assert mock_config_entries.flow.mock_calls[0][2]['data'] == {
        'host': '0.0.0.0',
        'path': 'bla.conf',
    }

    # Config stored for domain.
    assert hass.data[hue.DOMAIN] == {
        '0.0.0.0': {
            hue.CONF_HOST: '0.0.0.0',
            hue.CONF_FILENAME: 'bla.conf',
            hue.CONF_ALLOW_HUE_GROUPS: False,
            hue.CONF_ALLOW_UNREACHABLE: True
        }
    }


async def test_config_passed_to_config_entry(hass):
    """Test that configured options for a host are loaded via config entry."""
    entry = MockConfigEntry(domain=hue.DOMAIN, data={
        'host': '0.0.0.0',
    })
    entry.add_to_hass(hass)

    with patch.object(hue, 'HueBridge') as mock_bridge:
        mock_bridge.return_value.async_setup.return_value = mock_coro(True)
        assert await async_setup_component(hass, hue.DOMAIN, {
            hue.DOMAIN: {
                hue.CONF_BRIDGES: {
                    hue.CONF_HOST: '0.0.0.0',
                    hue.CONF_FILENAME: 'bla.conf',
                    hue.CONF_ALLOW_HUE_GROUPS: False,
                    hue.CONF_ALLOW_UNREACHABLE: True
                }
            }
        }) is True

    assert len(mock_bridge.mock_calls) == 2
    p_hass, p_entry, p_allow_unreachable, p_allow_groups = \
        mock_bridge.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry is entry
    assert p_allow_unreachable is True
    assert p_allow_groups is False


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(domain=hue.DOMAIN, data={
        'host': '0.0.0.0',
    })
    entry.add_to_hass(hass)

    with patch.object(hue, 'HueBridge') as mock_bridge:
        mock_bridge.return_value.async_setup.return_value = mock_coro(True)
        assert await async_setup_component(hass, hue.DOMAIN, {}) is True

    assert len(mock_bridge.return_value.mock_calls) == 1

    mock_bridge.return_value.async_reset.return_value = mock_coro(True)
    assert await hue.async_unload_entry(hass, entry)
    assert len(mock_bridge.return_value.async_reset.mock_calls) == 1
    assert hass.data[hue.DOMAIN] == {}
