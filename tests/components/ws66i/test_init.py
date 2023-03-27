"""Test the WS66i 6-Zone Amplifier init file."""
from unittest.mock import patch

from homeassistant.components.ws66i.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .test_media_player import (
    MOCK_CONFIG,
    MOCK_DEFAULT_OPTIONS,
    MOCK_OPTIONS,
    MockWs66i,
)

from tests.common import MockConfigEntry

ZONE_1_ID = "media_player.zone_11"


async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_OPTIONS
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: MockWs66i(fail_open=True),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.SETUP_RETRY
        assert hass.states.get(ZONE_1_ID) is None


async def test_cannot_connect_2(hass: HomeAssistant) -> None:
    """Test connection error pt 2."""
    # Another way to test same case as test_cannot_connect
    ws66i = MockWs66i()
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_DEFAULT_OPTIONS
    )
    config_entry.add_to_hass(hass)

    with patch.object(MockWs66i, "open", side_effect=ConnectionError):
        with patch(
            "homeassistant.components.ws66i.get_ws66i",
            new=lambda *a: ws66i,
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.SETUP_RETRY
        assert hass.states.get(ZONE_1_ID) is None


async def test_unload_config_entry(hass: HomeAssistant) -> None:
    """Test unloading config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_OPTIONS
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: MockWs66i(),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN][config_entry.entry_id]

    with patch.object(MockWs66i, "close") as method_call:
        await config_entry.async_unload(hass)
        await hass.async_block_till_done()

        assert method_call.called

    assert not hass.data[DOMAIN]
