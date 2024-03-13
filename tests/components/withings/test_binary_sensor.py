"""Tests for the Withings component."""

from unittest.mock import AsyncMock

from aiohttp.client_exceptions import ClientResponseError
from aiowithings import NotificationCategory
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import call_webhook, prepare_webhook_setup, setup_integration
from .conftest import USER_ID, WEBHOOK_ID

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_binary_sensor(
    hass: HomeAssistant,
    withings: AsyncMock,
    webhook_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test binary sensor."""
    await setup_integration(hass, webhook_config_entry)
    await prepare_webhook_setup(hass, freezer)

    client = await hass_client_no_auth()

    entity_id = "binary_sensor.henk_in_bed"

    assert hass.states.get(entity_id) is None

    resp = await call_webhook(
        hass,
        WEBHOOK_ID,
        {"userid": USER_ID, "appli": NotificationCategory.IN_BED},
        client,
    )
    assert resp.message_code == 0
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    resp = await call_webhook(
        hass,
        WEBHOOK_ID,
        {"userid": USER_ID, "appli": NotificationCategory.OUT_BED},
        client,
    )
    assert resp.message_code == 0
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.config_entries.async_reload(webhook_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert (
        "Platform withings does not generate unique IDs. ID withings_12345_in_bed "
        "already exists - ignoring binary_sensor.henk_in_bed" not in caplog.text
    )


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

    assert hass.states.get(entity_id) is None

    with pytest.raises(ClientResponseError):
        await call_webhook(
            hass,
            WEBHOOK_ID,
            {"userid": USER_ID, "appli": NotificationCategory.IN_BED},
            client,
        )
