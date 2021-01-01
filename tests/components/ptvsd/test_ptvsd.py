"""Tests for PTVSD Debugger."""

from unittest.mock import AsyncMock, patch

from pytest import mark

from homeassistant.bootstrap import _async_set_up_integrations
import homeassistant.components.ptvsd as ptvsd_component
from homeassistant.setup import async_setup_component


@mark.skip("causes code cover to fail")
async def test_ptvsd(hass):
    """Test loading ptvsd component."""
    with patch("ptvsd.enable_attach") as attach:
        with patch("ptvsd.wait_for_attach") as wait:
            assert await async_setup_component(
                hass, ptvsd_component.DOMAIN, {ptvsd_component.DOMAIN: {}}
            )

            attach.assert_called_once_with(("0.0.0.0", 5678))
            assert wait.call_count == 0


@mark.skip("causes code cover to fail")
async def test_ptvsd_wait(hass):
    """Test loading ptvsd component with wait."""
    with patch("ptvsd.enable_attach") as attach:
        with patch("ptvsd.wait_for_attach") as wait:
            assert await async_setup_component(
                hass,
                ptvsd_component.DOMAIN,
                {ptvsd_component.DOMAIN: {ptvsd_component.CONF_WAIT: True}},
            )

            attach.assert_called_once_with(("0.0.0.0", 5678))
            assert wait.call_count == 1


async def test_ptvsd_bootstrap(hass):
    """Test loading ptvsd component with wait."""
    config = {ptvsd_component.DOMAIN: {ptvsd_component.CONF_WAIT: True}}

    with patch("homeassistant.components.ptvsd.async_setup", AsyncMock()) as setup_mock:
        setup_mock.return_value = True
        await _async_set_up_integrations(hass, config)

        assert setup_mock.call_count == 1
