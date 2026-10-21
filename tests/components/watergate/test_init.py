"""Tests for the Watergate integration init module."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import (
    ANY,
    AsyncMock,
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from watergate_local_api import WatergateApiException

from homeassistant.components.valve import ValveState
from homeassistant.components.watergate.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import init_integration
from .const import DEFAULT_DEVICE_STATE_V2, MOCK_WEBHOOK_ID

NEGATIVE_VOLUME_ENTITY_ID = "sensor.sonic_water_meter_negative_volume"


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test setting up the Watergate integration."""
    hass.config.internal_url = "http://hassio.local"

    with (
        patch("homeassistant.components.watergate.async_register") as mock_webhook,
    ):
        await init_integration(hass, mock_entry)

        assert mock_entry.state is ConfigEntryState.LOADED

        mock_webhook.assert_called_once_with(
            hass,
            DOMAIN,
            "Watergate",
            MOCK_WEBHOOK_ID,
            ANY,
        )
        mock_watergate_client.async_set_webhook_url.assert_called_once_with(
            f"http://hassio.local/api/webhook/{MOCK_WEBHOOK_ID}"
        )
        mock_watergate_client.async_get_device_state_v2.assert_called_once()


async def test_handle_webhook(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test handling webhook events."""
    await init_integration(hass, mock_entry)

    entity_id = "valve.sonic"

    registered_entity = hass.states.get(entity_id)
    assert registered_entity
    assert registered_entity.state == ValveState.OPEN

    valve_change_data = {
        "type": "valve",
        "data": {"state": "closed"},
    }
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=valve_change_data)

    await hass.async_block_till_done()  # Ensure the webhook is processed

    assert hass.states.get(entity_id).state == ValveState.CLOSED

    valve_change_data = {
        "type": "valve",
        "data": {"state": "open"},
    }

    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=valve_change_data)

    await hass.async_block_till_done()  # Ensure the webhook is processed

    assert hass.states.get(entity_id).state == ValveState.OPEN


async def test_coordinator_fetches_auto_shut_off(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """Coordinator stores auto-shut-off state fetched from the client."""
    await init_integration(hass, mock_entry)

    mock_watergate_client.async_get_auto_shut_off.assert_called_once()
    assert hass.states.get("switch.sonic_auto_shut_off").state == STATE_ON


async def test_setup_retry_when_device_unavailable(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """Setup is retried when a device read fails during the first refresh."""
    mock_watergate_client.async_get_device_state_v2.side_effect = WatergateApiException(
        "boom"
    )
    mock_watergate_client.async_get_device_state.side_effect = WatergateApiException(
        "boom"
    )

    await init_integration(hass, mock_entry)

    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_state_missing_from_the_v1_fallback(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device reporting no state at all leaves the coordinator without one."""
    mock_watergate_client.async_get_device_state_v2.side_effect = WatergateApiException(
        "Unsupported media type"
    )
    await init_integration(hass, mock_entry)

    mock_watergate_client.async_get_device_state.return_value = None
    freezer.tick(timedelta(minutes=2, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.sonic_water_meter_volume").state == STATE_UNAVAILABLE


async def test_device_state_v2_is_not_probed_again_after_falling_back(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that v2 is not probed on every update once the firmware has rejected it."""
    mock_watergate_client.async_get_device_state_v2.side_effect = WatergateApiException(
        "Unsupported media type"
    )

    await init_integration(hass, mock_entry)

    freezer.tick(timedelta(minutes=2, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_watergate_client.async_get_device_state_v2.call_count == 2
    assert mock_watergate_client.async_get_device_state.call_count == 2


async def test_unreachable_device_does_not_fall_back_to_device_state_v1(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an update failing while the device is offline keeps v2 in use."""
    await init_integration(hass, mock_entry)

    mock_watergate_client.async_get_device_state_v2.side_effect = WatergateApiException(
        "boom"
    )
    mock_watergate_client.async_get_device_state.side_effect = WatergateApiException(
        "boom"
    )
    freezer.tick(timedelta(minutes=2, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_watergate_client.async_get_device_state_v2.side_effect = None
    mock_watergate_client.async_get_device_state.side_effect = None
    freezer.tick(timedelta(minutes=2, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(NEGATIVE_VOLUME_ENTITY_ID).state == "0.3"


async def test_device_state_v2_survives_a_blip_that_ends_during_the_first_update(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
) -> None:
    """Test that v2 is kept when the device is back by the time v1 is read."""
    mock_watergate_client.async_get_device_state_v2.side_effect = [
        WatergateApiException("blip"),
        DEFAULT_DEVICE_STATE_V2,
    ]

    await init_integration(hass, mock_entry)

    assert hass.states.get(NEGATIVE_VOLUME_ENTITY_ID).state == "0.3"
    assert mock_watergate_client.async_get_device_state_v2.call_count == 2


async def test_confirmed_device_state_v2_is_never_downgraded(
    hass: HomeAssistant,
    mock_watergate_client: Generator[AsyncMock],
    mock_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a v2 failure after v2 was read fails the update without using v1."""
    await init_integration(hass, mock_entry)
    mock_watergate_client.async_get_device_state.reset_mock()

    mock_watergate_client.async_get_device_state_v2.side_effect = WatergateApiException(
        "blip"
    )
    freezer.tick(timedelta(minutes=2, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(NEGATIVE_VOLUME_ENTITY_ID).state == STATE_UNAVAILABLE
    mock_watergate_client.async_get_device_state.assert_not_called()

    mock_watergate_client.async_get_device_state_v2.side_effect = None
    freezer.tick(timedelta(minutes=2, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(NEGATIVE_VOLUME_ENTITY_ID).state == "0.3"
