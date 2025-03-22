"""Test the wmspro cover support."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.wmspro.const import DOMAIN
from homeassistant.components.wmspro.cover import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_OPEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_config_entry

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_cover_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod_awning_dimmer: AsyncMock,
    mock_hub_status_prod_awning: AsyncMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a cover device is created correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod_awning_dimmer.mock_calls) == 1
    assert len(mock_hub_status_prod_awning.mock_calls) == 2

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "58717")})
    assert device_entry is not None
    assert device_entry == snapshot


async def test_cover_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod_awning_dimmer: AsyncMock,
    mock_hub_status_prod_awning: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a cover entity is created and updated correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod_awning_dimmer.mock_calls) == 1
    assert len(mock_hub_status_prod_awning.mock_calls) == 2

    entity = hass.states.get("cover.markise")
    assert entity is not None
    assert entity == snapshot

    # Move time to next update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_hub_status_prod_awning.mock_calls) >= 3


async def test_cover_open_and_close(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod_awning_dimmer: AsyncMock,
    mock_hub_status_prod_awning: AsyncMock,
    mock_action_call: AsyncMock,
) -> None:
    """Test that a cover entity is opened and closed correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod_awning_dimmer.mock_calls) == 1
    assert len(mock_hub_status_prod_awning.mock_calls) >= 1

    entity = hass.states.get("cover.markise")
    assert entity is not None
    assert entity.state == STATE_CLOSED
    assert entity.attributes["current_position"] == 0

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_awning.mock_calls)

        await hass.services.async_call(
            Platform.COVER,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get("cover.markise")
        assert entity is not None
        assert entity.state == STATE_OPEN
        assert entity.attributes["current_position"] == 100
        assert len(mock_hub_status_prod_awning.mock_calls) == before

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_awning.mock_calls)

        await hass.services.async_call(
            Platform.COVER,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get("cover.markise")
        assert entity is not None
        assert entity.state == STATE_CLOSED
        assert entity.attributes["current_position"] == 0
        assert len(mock_hub_status_prod_awning.mock_calls) == before


async def test_cover_open_to_pos(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod_awning_dimmer: AsyncMock,
    mock_hub_status_prod_awning: AsyncMock,
    mock_action_call: AsyncMock,
) -> None:
    """Test that a cover entity is opened to correct position."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod_awning_dimmer.mock_calls) == 1
    assert len(mock_hub_status_prod_awning.mock_calls) >= 1

    entity = hass.states.get("cover.markise")
    assert entity is not None
    assert entity.state == STATE_CLOSED
    assert entity.attributes["current_position"] == 0

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_awning.mock_calls)

        await hass.services.async_call(
            Platform.COVER,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity.entity_id, "position": 50},
            blocking=True,
        )

        entity = hass.states.get("cover.markise")
        assert entity is not None
        assert entity.state == STATE_OPEN
        assert entity.attributes["current_position"] == 50
        assert len(mock_hub_status_prod_awning.mock_calls) == before


async def test_cover_open_and_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod_awning_dimmer: AsyncMock,
    mock_hub_status_prod_awning: AsyncMock,
    mock_action_call: AsyncMock,
) -> None:
    """Test that a cover entity is opened and stopped correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod_awning_dimmer.mock_calls) == 1
    assert len(mock_hub_status_prod_awning.mock_calls) >= 1

    entity = hass.states.get("cover.markise")
    assert entity is not None
    assert entity.state == STATE_CLOSED
    assert entity.attributes["current_position"] == 0

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_awning.mock_calls)

        await hass.services.async_call(
            Platform.COVER,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity.entity_id, "position": 80},
            blocking=True,
        )

        entity = hass.states.get("cover.markise")
        assert entity is not None
        assert entity.state == STATE_OPEN
        assert entity.attributes["current_position"] == 80
        assert len(mock_hub_status_prod_awning.mock_calls) == before

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_awning.mock_calls)

        await hass.services.async_call(
            Platform.COVER,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get("cover.markise")
        assert entity is not None
        assert entity.state == STATE_OPEN
        assert entity.attributes["current_position"] == 80
        assert len(mock_hub_status_prod_awning.mock_calls) == before
