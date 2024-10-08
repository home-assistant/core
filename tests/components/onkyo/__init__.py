"""Tests for the Onkyo integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.onkyo.const import DOMAIN, OPTION_INPUT_SOURCES
from homeassistant.components.onkyo.receiver import Receiver, ReceiverInfo
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def _mock_async_create(info):
    return AsyncMock()


def create_empty_receiver_info() -> ReceiverInfo:
    """Create an empty receiver info object for testing."""
    return ReceiverInfo(
        host="",
        port=0,
        model_name="",
        identifier="",
    )


def create_empty_config_entry() -> MockConfigEntry:
    """Create an empty config entry for use in unit tests."""
    config = {CONF_HOST: ""}
    options = {OPTION_INPUT_SOURCES: {}}

    return MockConfigEntry(
        data=config,
        options=options,
        title="Unit test Onkyo",
        domain=DOMAIN,
        unique_id="airzone_unique_id",
    )


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, receiver_info: ReceiverInfo
) -> None:
    """Fixture for setting up the component."""

    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.onkyo.async_interview",
            return_value=receiver_info,
        ),
        patch.object(Receiver, "async_create", _mock_async_create),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
