"""Tests for event entity."""
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from withings_api.common import NotifyAppli

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import call_webhook, enable_webhooks, setup_integration
from .conftest import USER_ID, WEBHOOK_ID

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2023-08-01 00:00:00")
async def test_sleep_event(
    hass: HomeAssistant,
    withings: AsyncMock,
    disable_webhook_delay,
    webhook_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sleep event."""
    await enable_webhooks(hass)
    await setup_integration(hass, webhook_config_entry)

    client = await hass_client_no_auth()

    entity_id = "event.henk_bed_activity"

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    resp = await call_webhook(
        hass,
        WEBHOOK_ID,
        {"userid": USER_ID, "appli": NotifyAppli.BED_IN},
        client,
    )
    assert resp.message_code == 0
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "2023-08-01T00:00:00.000+00:00"

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)

    resp = await call_webhook(
        hass,
        WEBHOOK_ID,
        {"userid": USER_ID, "appli": NotifyAppli.BED_OUT},
        client,
    )
    assert resp.message_code == 0
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "2023-08-01T00:10:00.000+00:00"
