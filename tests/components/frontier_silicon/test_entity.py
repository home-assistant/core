"""Test the Frontier Silicon base entity."""

from typing import override
from unittest.mock import AsyncMock

from afsapi import AFSAPI, FSConnectionError
import pytest

from homeassistant.components.frontier_silicon import FrontierSiliconConfigEntry
from homeassistant.components.frontier_silicon.entity import FrontierSiliconEntity

from tests.common import MockConfigEntry


class FSTestEntity(FrontierSiliconEntity):
    """Minimal test entity subclass."""

    def __init__(
        self,
        config_entry: FrontierSiliconConfigEntry,
        afsapi: AFSAPI,
        raise_error: bool,
    ) -> None:
        """Initialize the Frontier Silicon API device."""
        super().__init__(afsapi, config_entry)
        self.raise_error = raise_error

    @override
    async def _fs_update(self) -> None:
        if self.raise_error:
            raise FSConnectionError


async def test_base_entity_update() -> None:
    """Test that base entity async_update results in a NotImplementedError."""
    fs_device = AsyncMock()
    mock_config_entry = MockConfigEntry()
    base_entity = FrontierSiliconEntity(fs_device, mock_config_entry)
    with pytest.raises(NotImplementedError):
        await base_entity.async_update()


@pytest.mark.parametrize("raise_error", [True, False])
async def test_base_entity_subclass_update(raise_error: bool) -> None:
    """Test that base entity subclass async_update changes entity availability."""
    fs_device = AsyncMock()
    mock_config_entry = MockConfigEntry()
    test_entity = FSTestEntity(mock_config_entry, fs_device, raise_error)
    await test_entity.async_update()
    assert raise_error != test_entity.available
