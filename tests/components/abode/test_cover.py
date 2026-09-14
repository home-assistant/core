"""Tests for the Abode cover device."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_CLOSE_COVER, SERVICE_OPEN_COVER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import snapshot_platform

DEVICE_ID = "cover.garage_door"


async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities."""
    config_entry = await setup_platform(hass, COVER_DOMAIN)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_open(hass: HomeAssistant) -> None:
    """Test the cover can be opened."""
    await setup_platform(hass, COVER_DOMAIN)

    with patch("jaraco.abode.devices.cover.Cover.open_cover") as mock_open:
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
        await hass.async_block_till_done()
        mock_open.assert_called_once()


async def test_close(hass: HomeAssistant) -> None:
    """Test the cover can be closed."""
    await setup_platform(hass, COVER_DOMAIN)

    with patch("jaraco.abode.devices.cover.Cover.close_cover") as mock_close:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_close.assert_called_once()
