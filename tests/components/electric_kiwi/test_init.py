"""Tests for the Electric Kiwi component."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components import electric_kiwi
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.usefixtures("setup_credentials")
async def test_cloud_unique_id_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    ek_api: AsyncMock,
) -> None:
    """Test that the unique ID is migrated to the customer number."""

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)

    await electric_kiwi.async_migrate_entry(hass, config_entry)

    await hass.async_block_till_done()
    new_entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert new_entry.unique_id == "123456"
