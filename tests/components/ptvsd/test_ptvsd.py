"""Tests for PTVSD Debugger."""


from unittest.mock import patch

import homeassistant.components.ptvsd as ptvsd_component
from homeassistant.setup import async_setup_component
from homeassistant.bootstrap import async_from_config_dict


async def test_ptvsd(hass):
    """Test loading ptvsd component."""
    with patch('ptvsd.enable_attach') as attach:
        with patch('ptvsd.wait_for_attach') as wait:
            assert await async_setup_component(
                hass, ptvsd_component.DOMAIN, {
                    ptvsd_component.DOMAIN: {}
                })

            attach.assert_called_once_with(('0.0.0.0', 5678))
            wait.assert_not_called()


async def test_ptvsd_wait(hass):
    """Test loading ptvsd component with wait."""
    with patch('ptvsd.enable_attach') as attach:
        with patch('ptvsd.wait_for_attach') as wait:
            assert await async_setup_component(
                hass, ptvsd_component.DOMAIN, {
                    ptvsd_component.DOMAIN: {
                        ptvsd_component.CONF_WAIT: True
                    }
                })

            attach.assert_called_once_with(('0.0.0.0', 5678))
            wait.assert_called_once()


async def test_ptvsd_bootstrap(hass):
    """Test loading ptvsd component with wait."""
    config = {
        ptvsd_component.DOMAIN: {
            ptvsd_component.CONF_WAIT: True
        }
    }

    with patch('ptvsd.enable_attach') as attach:
        with patch('ptvsd.wait_for_attach') as wait:
            await async_from_config_dict(config, hass)

            attach.assert_called_once_with(('0.0.0.0', 5678))
            wait.assert_called_once()
