"""Test Statistics component setup process."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant.components.compensation.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test unload an entry."""

    assert loaded_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_could_not_setup(hass: HomeAssistant, get_config: dict[str, Any]) -> None:
    """Test exception."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Compensation sensor",
        source=SOURCE_USER,
        options=get_config,
        entry_id="1",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.compensation.np.polyfit",
        side_effect=FloatingPointError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.error_reason_translation_key == "setup_error"
