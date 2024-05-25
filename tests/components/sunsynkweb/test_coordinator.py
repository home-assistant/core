"""Basic coordinator tests."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.sunsynkweb import (
    DOMAIN,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.sunsynkweb.coordinator import PlantUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_creation_destruction(hass, basicdata):
    """Check we can create and destroy the coordinator."""
    with patch(
        "homeassistant.components.sunsynkweb.coordinator.async_get_clientsession",
        new=Mock(),
    ) as sessiongetter:
        session = AsyncMock()
        sessiongetter.return_value = session
        mockedjson_return = AsyncMock()
        mockedjson_return.name = "mocked_json_return"
        session.get.return_value = mockedjson_return
        session.post.return_value = mockedjson_return
        mockedjson_return.json.side_effect = basicdata
        config = MockConfigEntry(data={"username": "blah", "password": "blahblah"})
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        await async_setup_entry(hass, config)
        coordinator = hass.data[DOMAIN][config.entry_id]
        assert len(coordinator.cache.plants) == 2
        await async_unload_entry(hass, config)
        assert config.entry_id not in hass.data[DOMAIN]


async def test_coordinator(hass, basicdata) -> None:
    """Run coordinator tests."""
    config = MockConfigEntry()
    coordinator = PlantUpdateCoordinator(hass, config)
    assert coordinator.cache is None
    assert coordinator.bearer is None
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    config = MockConfigEntry(data={"username": "blah", "password": "blahblah"})
    coordinator = PlantUpdateCoordinator(hass, config)
    coordinator.session = AsyncMock()
    mockedjson_return = AsyncMock()
    mockedjson_return.name = "mocked_json_return"
    coordinator.session.get.return_value = mockedjson_return
    coordinator.session.post.return_value = mockedjson_return
    mockedjson_return.json.side_effect = basicdata
    await coordinator._async_update_data()
    assert coordinator.cache is not None
    assert len(coordinator.cache.plants) == 2
    plant1, plant2 = coordinator.cache.plants
    assert plant1.load_power == 3
    assert plant1.ismaster() is True
    assert plant2.load_power == 3
