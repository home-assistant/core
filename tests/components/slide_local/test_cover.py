"""Tests for the Slide Local cover platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from goslideapi.goslideapi import ClientConnectionError
from syrupy import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform
from .const import SLIDE_INFO_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_connection_error(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test connection error."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])

    mock_slide_api.slide_info.side_effect = [ClientConnectionError, SLIDE_INFO_DATA]

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == STATE_UNAVAILABLE

    freezer.tick(delta=timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.OPEN


async def test_state_change(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test connection error."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])

    mock_slide_api.slide_info.side_effect = [
        dict(SLIDE_INFO_DATA, pos=0.0),
        dict(SLIDE_INFO_DATA, pos=0.4),
        dict(SLIDE_INFO_DATA, pos=1.0),
        dict(SLIDE_INFO_DATA, pos=0.8),
    ]

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.OPEN

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.CLOSING

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.CLOSED

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.OPENING


async def test_open_cover(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test open cover."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {
            ATTR_ENTITY_ID: "cover.slide_bedroom",
        },
        blocking=True,
    )
    mock_slide_api.slide_open.assert_called_once()


async def test_close_cover(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test close cover."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {
            ATTR_ENTITY_ID: "cover.slide_bedroom",
        },
        blocking=True,
    )
    mock_slide_api.slide_close.assert_called_once()


async def test_stop_cover(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stop cover."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {
            ATTR_ENTITY_ID: "cover.slide_bedroom",
        },
        blocking=True,
    )
    mock_slide_api.slide_stop.assert_called_once()


async def test_set_position(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test set cover position."""

    await setup_platform(hass, mock_config_entry, [Platform.COVER])

    mock_slide_api.slide_info.side_effect = [
        dict(SLIDE_INFO_DATA, pos=0.0),
        dict(SLIDE_INFO_DATA, pos=1.0),
        dict(SLIDE_INFO_DATA, pos=1.0),
        dict(SLIDE_INFO_DATA, pos=0.0),
    ]

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.slide_bedroom", ATTR_POSITION: 1.0},
        blocking=True,
    )

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.CLOSED

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.slide_bedroom", ATTR_POSITION: 0.0},
        blocking=True,
    )

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.OPEN

    assert len(mock_slide_api.slide_set_position.mock_calls) == 2
