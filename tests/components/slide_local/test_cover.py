"""Tests for the Slide Local cover platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from goslideapi.goslideapi import ClientConnectionError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverService,
    CoverServiceArgument,
    CoverState,
)
from homeassistant.const import STATE_UNAVAILABLE, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_data, setup_platform


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

    assert hass.states.get("cover.slide_bedroom").state == CoverState.OPEN

    mock_slide_api.slide_info.side_effect = [ClientConnectionError, get_data()]

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
    """Test state changes."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])

    mock_slide_api.slide_info.return_value = {
        **get_data(),
        "pos": 0.0,
    }

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.OPEN

    mock_slide_api.slide_info.return_value = {**get_data(), "pos": 0.4}

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.CLOSING

    mock_slide_api.slide_info.return_value = {**get_data(), "pos": 1.0}

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.CLOSED

    mock_slide_api.slide_info.return_value = {**get_data(), "pos": 0.8}

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
        CoverService.OPEN,
        {
            TargetKey.ENTITY_ID: "cover.slide_bedroom",
        },
        blocking=True,
    )
    mock_slide_api.slide_open.assert_called_once()
    assert hass.states.get("cover.slide_bedroom").state == CoverState.OPENING


async def test_close_cover(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test close cover."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.CLOSE,
        {
            TargetKey.ENTITY_ID: "cover.slide_bedroom",
        },
        blocking=True,
    )
    mock_slide_api.slide_close.assert_called_once()
    assert hass.states.get("cover.slide_bedroom").state == CoverState.CLOSING


@pytest.mark.parametrize(
    ("service", "api_method", "data"),
    [
        (CoverService.OPEN, "slide_open", {}),
        (CoverService.CLOSE, "slide_close", {}),
        (
            CoverService.SET_POSITION,
            "slide_set_position",
            {CoverServiceArgument.POSITION: 0},
        ),
    ],
)
async def test_command_failure_keeps_state(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    api_method: str,
    data: dict[str, int],
) -> None:
    """Test a failed command does not change the cover state."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])
    getattr(mock_slide_api, api_method).side_effect = ClientConnectionError

    with pytest.raises(ClientConnectionError):
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {TargetKey.ENTITY_ID: "cover.slide_bedroom", **data},
            blocking=True,
        )

    assert hass.states.get("cover.slide_bedroom").state == CoverState.OPEN

    assert mock_config_entry.runtime_data.data["state"] == CoverState.OPEN


async def test_stop_cover(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stop cover."""
    await setup_platform(hass, mock_config_entry, [Platform.COVER])

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.STOP,
        {
            TargetKey.ENTITY_ID: "cover.slide_bedroom",
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

    mock_slide_api.slide_info.return_value = {**get_data(), "pos": 0.0}

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_POSITION,
        {
            TargetKey.ENTITY_ID: "cover.slide_bedroom",
            CoverServiceArgument.POSITION: 1.0,
        },
        blocking=True,
    )
    assert hass.states.get("cover.slide_bedroom").state == CoverState.CLOSING

    mock_slide_api.slide_info.return_value = {**get_data(), "pos": 1.0}

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.CLOSED

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_POSITION,
        {
            TargetKey.ENTITY_ID: "cover.slide_bedroom",
            CoverServiceArgument.POSITION: 0.0,
        },
        blocking=True,
    )

    mock_slide_api.slide_info.return_value = {**get_data(), "pos": 0.0}

    freezer.tick(delta=timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("cover.slide_bedroom").state == CoverState.OPEN

    assert len(mock_slide_api.slide_set_position.mock_calls) == 2
