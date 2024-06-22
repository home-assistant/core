"""Test Linear Garage Door cover."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
)
from homeassistant.components.linear_garage_door import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
    snapshot_platform,
)


async def test_covers(
    hass: HomeAssistant,
    mock_linear: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that data gets parsed and returned appropriately."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_open_cover(
    hass: HomeAssistant, mock_linear: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test that opening the cover works as intended."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_garage_1"},
        blocking=True,
    )

    assert mock_linear.operate_device.call_count == 0

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_garage_2"},
        blocking=True,
    )

    assert mock_linear.operate_device.call_count == 1


async def test_close_cover(
    hass: HomeAssistant, mock_linear: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test that closing the cover works as intended."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_garage_2"},
        blocking=True,
    )

    assert mock_linear.operate_device.call_count == 0

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_garage_1"},
        blocking=True,
    )

    assert mock_linear.operate_device.call_count == 1


async def test_update_cover_state(
    hass: HomeAssistant,
    mock_linear: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that closing the cover works as intended."""

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert hass.states.get("cover.test_garage_1").state == STATE_OPEN
    assert hass.states.get("cover.test_garage_2").state == STATE_CLOSED

    device_states = load_json_object_fixture("get_device_state_1.json", DOMAIN)
    mock_linear.get_device_state.side_effect = lambda device_id: device_states[
        device_id
    ]

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)

    assert hass.states.get("cover.test_garage_1").state == STATE_CLOSING
    assert hass.states.get("cover.test_garage_2").state == STATE_OPENING
