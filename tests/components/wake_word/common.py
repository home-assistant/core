"""Provide common test tools for wake-word-detection."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from homeassistant.components import wake_word
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import MockPlatform, mock_platform


def mock_wake_word_entity_platform(
    hass: HomeAssistant,
    tmp_path: Path,
    integration: str,
    async_setup_entry: Callable[
        [HomeAssistant, ConfigEntry, AddEntitiesCallback],
        Coroutine[Any, Any, None],
    ]
    | None = None,
) -> MockPlatform:
    """Specialize the mock platform for stt."""
    loaded_platform = MockPlatform(async_setup_entry=async_setup_entry)
    mock_platform(hass, f"{integration}.{wake_word.DOMAIN}", loaded_platform)
    return loaded_platform
