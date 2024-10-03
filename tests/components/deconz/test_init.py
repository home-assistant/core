"""Test deCONZ component setup process."""

import asyncio
from unittest.mock import patch

import pydeconz
import pytest

from homeassistant.components.deconz.const import (
    CONF_MASTER_GATEWAY,
    DOMAIN as DECONZ_DOMAIN,
)
from homeassistant.components.deconz.errors import AuthenticationRequired
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import ConfigEntryFactoryType

from tests.common import MockConfigEntry


async def test_setup_entry(config_entry_setup: MockConfigEntry) -> None:
    """Test successful setup of entry."""
    assert config_entry_setup.state is ConfigEntryState.LOADED
    assert config_entry_setup.options[CONF_MASTER_GATEWAY] is True


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        # Failed authentication trigger a reauthentication flow
        (pydeconz.Unauthorized, ConfigEntryState.SETUP_ERROR),
        # Connection fails
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (pydeconz.RequestError, ConfigEntryState.SETUP_RETRY),
        (pydeconz.ResponseError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_get_deconz_api_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    side_effect: Exception,
    state: ConfigEntryState,
) -> None:
    """Failed setup."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.deconz.hub.api.DeconzSession.refresh_state",
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is state


async def test_setup_entry_fails_trigger_reauth_flow(
    hass: HomeAssistant, config_entry_factory: ConfigEntryFactoryType
) -> None:
    """Failed authentication trigger a reauthentication flow."""
    with (
        patch(
            "homeassistant.components.deconz.get_deconz_api",
            side_effect=AuthenticationRequired,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_flow_init,
    ):
        config_entry = await config_entry_factory()
        mock_flow_init.assert_called_once()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_multiple_gateways(
    hass: HomeAssistant, config_entry_factory: ConfigEntryFactoryType
) -> None:
    """Test setup entry is successful with multiple gateways."""
    config_entry = await config_entry_factory()

    entry2 = MockConfigEntry(
        domain=DECONZ_DOMAIN,
        entry_id="2",
        unique_id="01234E56789B",
        data=config_entry.data | {"host": "2.3.4.5"},
    )
    config_entry2 = await config_entry_factory(entry2)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry2.state is ConfigEntryState.LOADED
    assert config_entry.options[CONF_MASTER_GATEWAY] is True
    assert config_entry2.options[CONF_MASTER_GATEWAY] is False


async def test_unload_entry(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test being able to unload an entry."""
    assert config_entry_setup.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(config_entry_setup.entry_id)
    assert config_entry_setup.state is ConfigEntryState.NOT_LOADED


async def test_unload_entry_multiple_gateways(
    hass: HomeAssistant, config_entry_factory: ConfigEntryFactoryType
) -> None:
    """Test being able to unload an entry and master gateway gets moved."""
    config_entry = await config_entry_factory()

    entry2 = MockConfigEntry(
        domain=DECONZ_DOMAIN,
        entry_id="2",
        unique_id="01234E56789B",
        data=config_entry.data | {"host": "2.3.4.5"},
    )
    config_entry2 = await config_entry_factory(entry2)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry2.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry2.options[CONF_MASTER_GATEWAY] is True


async def test_unload_entry_multiple_gateways_parallel(
    hass: HomeAssistant, config_entry_factory: ConfigEntryFactoryType
) -> None:
    """Test race condition when unloading multiple config entries in parallel."""
    config_entry = await config_entry_factory()

    entry2 = MockConfigEntry(
        domain=DECONZ_DOMAIN,
        entry_id="2",
        unique_id="01234E56789B",
        data=config_entry.data | {"host": "2.3.4.5"},
    )
    config_entry2 = await config_entry_factory(entry2)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry2.state is ConfigEntryState.LOADED

    await asyncio.gather(
        hass.config_entries.async_unload(config_entry.entry_id),
        hass.config_entries.async_unload(config_entry2.entry_id),
    )

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry2.state is ConfigEntryState.NOT_LOADED
