"""Tests for PTVSD Debugger."""

from unittest.mock import patch
from asynctest import CoroutineMock

import homeassistant.components.ptvsd as ptvsd_component
from homeassistant.bootstrap import _async_set_up_integrations


async def test_ptvsd_bootstrap(hass):
    """Test loading ptvsd component with wait."""
    config = {
        ptvsd_component.DOMAIN: {
            ptvsd_component.CONF_WAIT: True
        }
    }

    with patch(
            'homeassistant.components.ptvsd.async_setup',
            CoroutineMock()) as setup_mock:
        await _async_set_up_integrations(hass, config)

        setup_mock.assert_called_once()
