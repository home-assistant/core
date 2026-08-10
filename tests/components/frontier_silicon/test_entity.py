"""Test the Frontier Silicon base entity."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.frontier_silicon.entity import FrontierSiliconEntity

from tests.common import MockConfigEntry


async def test_base_entity_update() -> None:
    """Test that base entity async_update results in a NotImplementedError."""
    fs_device = AsyncMock()
    mock_config_entry = MockConfigEntry()
    base_entity = FrontierSiliconEntity(mock_config_entry, fs_device)
    with pytest.raises(NotImplementedError):
        await base_entity.async_update()
