"""Test Onkyo component setup process."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.onkyo import async_setup_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from . import create_empty_config_entry, create_receiver_info, setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""

    config_entry = create_empty_config_entry()
    receiver_info = create_receiver_info(1)
    await setup_integration(hass, config_entry, receiver_info)

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_update_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test update options."""

    with patch.object(hass.config_entries, "async_reload", return_value=True):
        config_entry = create_empty_config_entry()
        receiver_info = create_receiver_info(1)
        await setup_integration(hass, config_entry, receiver_info)

        # Force option change
        assert hass.config_entries.async_update_entry(
            config_entry, options={"option": "new_value"}
        )
        await hass.async_block_till_done()

        hass.config_entries.async_reload.assert_called_with(config_entry.entry_id)


async def test_no_connection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test update options."""

    config_entry = create_empty_config_entry()
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.onkyo.async_interview",
            return_value=None,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, config_entry)
