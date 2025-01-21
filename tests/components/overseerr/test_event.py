"""Tests for the Overseerr event platform."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from future.backports.datetime import timedelta
import pytest
from python_overseerr import OverseerrConnectionError
from syrupy import SnapshotAssertion

from homeassistant.components.overseerr import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import call_webhook, setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
    snapshot_platform,
)
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2023-10-21")
async def test_entities(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.overseerr.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)

    client = await hass_client_no_auth()

    await call_webhook(
        hass,
        load_json_object_fixture("webhook_request_automatically_approved.json", DOMAIN),
        client,
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2023-10-21")
async def test_event_does_not_write_state(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event entities don't write state on coordinator update."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_client_no_auth()

    await call_webhook(
        hass,
        load_json_object_fixture("webhook_request_automatically_approved.json", DOMAIN),
        client,
    )
    await hass.async_block_till_done()

    assert hass.states.get(
        "event.overseerr_last_media_event"
    ).last_reported == datetime(2023, 10, 21, 0, 0, 0, tzinfo=UTC)

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(
        "event.overseerr_last_media_event"
    ).last_reported == datetime(2023, 10, 21, 0, 0, 0, tzinfo=UTC)


async def test_event_goes_unavailable(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event entities go unavailable when we can't fetch data."""
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("event.overseerr_last_media_event").state != STATE_UNAVAILABLE
    )

    mock_overseerr_client.get_request_count.side_effect = OverseerrConnectionError(
        "Boom"
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("event.overseerr_last_media_event").state == STATE_UNAVAILABLE
    )
