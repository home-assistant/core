"""Basic coordinator tests."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

from pysunsynkweb.model import Installation, Plant
import pytest

from homeassistant.components.sunsynkweb import (
    DOMAIN,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.sunsynkweb.coordinator import PlantUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_creation_destruction(
    hass: AsyncGenerator[HomeAssistant, None], basicdata: list
):
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


async def test_coordinator(
    hass: AsyncGenerator[HomeAssistant, None], basicdata: list
) -> None:
    """Run coordinator tests."""
    config = MockConfigEntry(data={"username": "blah", "password": "blahblah"})
    coordinator = PlantUpdateCoordinator(hass, config)
    with patch(
        "homeassistant.components.sunsynkweb.coordinator.get_plants"
    ) as mockedplants:
        patchedplant = Plant(1, 2, "plant1", 1)
        patchedplant.update = AsyncMock()
        mockedplants.return_value = Installation([patchedplant])
        await coordinator._async_update_data()
        mockedplants.assert_called_once()
        patchedplant.update.assert_called_once()
        patchedplant.update.side_effect = KeyError
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
