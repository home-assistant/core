"""Define tests for device-related endpoints."""

from datetime import timedelta
from unittest.mock import patch

from aioflo.errors import RequestError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Flo by Moen devices."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    call_count = aioclient_mock.call_count

    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == call_count + 6


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_device_failures(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Flo by Moen devices buffer API failures."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    def assert_state(state: str) -> None:
        assert (
            hass.states.get("sensor.smart_water_shutoff_current_system_mode").state
            == state
        )

    assert_state("home")

    async def move_time_and_assert_state(state: str) -> None:
        freezer.tick(timedelta(seconds=65))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert_state(state)

    aioclient_mock.clear_requests()
    with patch(
        "aioflo.presence.Presence.ping",
        side_effect=RequestError,
    ):
        # simulate 4 updates failing. The failures should be buffered so that it takes 4
        # consecutive failures to mark the device and entities as unavailable.
        await move_time_and_assert_state("home")
        await move_time_and_assert_state("home")
        await move_time_and_assert_state("home")
        await move_time_and_assert_state(STATE_UNAVAILABLE)
