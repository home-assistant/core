"""Tests for PTVSD Debugger."""


from unittest.mock import patch

import ptvsd  # noqa: F401

import homeassistant.components.ptvsd as ptvsd_component
from homeassistant.setup import async_setup_component
from homeassistant.bootstrap import _async_set_up_integrations


async def test_ptvsd(hass):
    """Test loading ptvsd component."""
    with patch('ptvsd.enable_attach') as attach:
        with patch('ptvsd.wait_for_attach') as wait:
            assert await async_setup_component(
                hass, ptvsd_component.DOMAIN, {
                    ptvsd_component.DOMAIN: {}
                })

            attach.assert_called_once_with(('0.0.0.0', 5678))
            assert wait.call_count == 0


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
            assert wait.call_count == 1


async def test_ptvsd_bootstrap(hass):
    """Test loading ptvsd component with wait."""
    config = {
        ptvsd_component.DOMAIN: {
            ptvsd_component.CONF_WAIT: True
        }
    }

    with patch('ptvsd.enable_attach') as attach:
        with patch('ptvsd.wait_for_attach') as wait:
            await _async_set_up_integrations(hass, config)

            attach.assert_called_once_with(('0.0.0.0', 5678))
            assert wait.call_count == 1
