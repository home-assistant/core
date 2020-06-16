"""Test Becker setup process."""
from unittest.mock import patch

from homeassistant.components import becker
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a cover."""
    assert await async_setup_component(hass, becker.DOMAIN, {}) is True

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0

    # No configs stored
    assert hass.data[becker.DOMAIN] == {}


async def test_setup_defined_cover(hass):
    """Test we don't initiate a config entry if config bridge is known."""

    MockConfigEntry(
        domain="becker", data={becker.CONF_DEVICE: becker.DEFAULT_CONF_USB_STICK_PATH}
    ).add_to_hass(hass)

    with patch.object(becker, "async_setup_entry", return_value=mock_coro(True)):
        assert (
            await async_setup_component(
                hass,
                becker.DOMAIN,
                {
                    becker.DOMAIN: {
                        becker.CONF_COVERS: [
                            {becker.CONF_CHANNEL: "1", becker.CONF_UNIT: "1"},
                        ]
                    }
                },
            )
            is True
        )

    # Config stored for domain.
    assert hass.data[becker.DOMAIN][becker.CONF_COVERS] == {
        "1": {becker.CONF_CHANNEL: "1", becker.CONF_UNIT: "1"}
    }
