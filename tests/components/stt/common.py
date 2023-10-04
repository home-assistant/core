"""Provide common test tools for STT."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from homeassistant.components.stt import Provider
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from tests.common import MockPlatform, mock_platform


class MockSTTPlatform(MockPlatform):
    """Help to set up test stt service."""

    def __init__(
        self,
        async_get_engine: Callable[
            [HomeAssistant, ConfigType, DiscoveryInfoType | None],
            Coroutine[Any, Any, Provider | None],
        ]
        | None = None,
        get_engine: Callable[
            [HomeAssistant, ConfigType, DiscoveryInfoType | None], Provider | None
        ]
        | None = None,
    ) -> None:
        """Return the stt service."""
        super().__init__()
        if get_engine:
            self.get_engine = get_engine
        if async_get_engine:
            self.async_get_engine = async_get_engine


def mock_stt_platform(
    hass: HomeAssistant,
    tmp_path: Path,
    integration: str = "stt",
    async_get_engine: Callable[
        [HomeAssistant, ConfigType, DiscoveryInfoType | None],
        Coroutine[Any, Any, Provider | None],
    ]
    | None = None,
    get_engine: Callable[
        [HomeAssistant, ConfigType, DiscoveryInfoType | None], Provider | None
    ]
    | None = None,
):
    """Specialize the mock platform for stt."""
    loaded_platform = MockSTTPlatform(async_get_engine, get_engine)
    mock_platform(hass, f"{integration}.stt", loaded_platform)

    return loaded_platform


def mock_stt_entity_platform(
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
    mock_platform(hass, f"{integration}.stt", loaded_platform)
    return loaded_platform
