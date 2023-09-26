"""Tests for binary sensor entity."""
from datetime import timedelta
from unittest.mock import AsyncMock

from aiohttp.client_exceptions import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
import pytest
from withings_api.common import NotifyAppli

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import call_webhook, setup_integration
from .conftest import USER_ID, WEBHOOK_ID

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator


async def test_sleep_event(
    hass: HomeAssistant,
    withings: AsyncMock,
    webhook_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sleep event."""
    await setup_integration(hass, webhook_config_entry)

    client = await hass_client_no_auth()

    entity_id = "binary_sensor.henk_in_bed"

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    resp = await call_webhook(
        hass,
        WEBHOOK_ID,
        {"userid": USER_ID, "appli": NotifyAppli.BED_IN},
        client,
    )
    assert resp.message_code == 0
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "on"

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
    state = hass.states.get(entity_id)
    assert state.state == "off"


async def test_polling_binary_sensor(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test binary sensor."""
    await setup_integration(hass, polling_config_entry, False)

    client = await hass_client_no_auth()

    entity_id = "binary_sensor.henk_in_bed"

    assert hass.states.get(entity_id).state is STATE_UNKNOWN

    with pytest.raises(ClientResponseError):
        await call_webhook(
            hass,
            WEBHOOK_ID,
            {"userid": USER_ID, "appli": NotifyAppli.BED_IN},
            client,
        )
