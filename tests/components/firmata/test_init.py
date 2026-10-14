"""Tests for the Firmata integration setup."""

from unittest.mock import patch

from homeassistant.components.firmata.const import CONF_SERIAL_PORT, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_board_failed(hass: HomeAssistant) -> None:
    """Test setup fails when the board can't be set up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "serial-/dev/nonExistent",
            CONF_SERIAL_PORT: "/dev/nonExistent",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.firmata.board.PymataExpress.start_aio",
        side_effect=RuntimeError,
    ):
        await async_setup_component(
            hass, DOMAIN, {DOMAIN: [{CONF_SERIAL_PORT: "/dev/nonExistent"}]}
        )
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Failed to set up Firmata board serial-/dev/nonExistent"
