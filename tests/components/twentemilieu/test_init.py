"""Tests for the Twente Milieu integration."""

from unittest.mock import MagicMock

import pytest
from twentemilieu import TwenteMilieuConnectionError, TwenteMilieuError

from homeassistant.components.twentemilieu.const import (
    CONF_HOUSE_LETTER,
    CONF_HOUSE_NUMBER,
    CONF_POST_CODE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_twentemilieu")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Twente Milieu configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect", [TwenteMilieuConnectionError, TwenteMilieuError]
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_twentemilieu: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
) -> None:
    """Test the Twente Milieu configuration entry not ready."""
    mock_twentemilieu.update.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_twentemilieu.update.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_twentemilieu")
async def test_migrate_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration of sensor entity unique IDs."""
    mock_config_entry = MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={
            CONF_ID: 12345,
            CONF_POST_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_HOUSE_LETTER: "A",
        },
        unique_id="12345",
    )
    mock_config_entry.add_to_hass(hass)

    old_to_new_unique_ids = {
        "twentemilieu_12345_tree": "12345_tree",
        "twentemilieu_12345_Non-recyclable": "12345_non_recyclable",
        "twentemilieu_12345_Organic": "12345_organic",
        "twentemilieu_12345_Paper": "12345_paper",
        "twentemilieu_12345_Plastic": "12345_packages",
    }
    for old_unique_id in old_to_new_unique_ids:
        entity_registry.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=old_unique_id,
            config_entry=mock_config_entry,
        )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    for old_unique_id, new_unique_id in old_to_new_unique_ids.items():
        assert (
            entity_registry.async_get_entity_id("sensor", DOMAIN, old_unique_id) is None
        )
        assert (
            entity_registry.async_get_entity_id("sensor", DOMAIN, new_unique_id)
            is not None
        )
