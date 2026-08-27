"""Test the BraviaTV coordinator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.braviatv.const import CONF_USE_PSK, DOMAIN
from homeassistant.components.braviatv.coordinator import BraviaTVCoordinator
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "start_datetime",
    [
        "2026-08-22T12:00:00",  # naive, treated as local time (CEST UTC+2)
        "2026-08-22T12:00:00+02:00",  # aware
    ],
)
@pytest.mark.freeze_time("2026-08-22T12:00:00+00:00")
async def test_async_update_playing(
    hass: HomeAssistant,
    start_datetime: str,
) -> None:
    """Test updating playing info with a start datetime."""
    await hass.config.async_set_time_zone("Europe/Warsaw")
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "localhost",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_USE_PSK: True,
            CONF_PIN: "12345qwerty",
        },
    )
    client = AsyncMock()
    client.get_playing_info.return_value = {"startDateTime": start_datetime}
    coordinator = BraviaTVCoordinator(hass, config_entry, client)

    await coordinator.async_update_playing()

    assert coordinator.media_position == 7200
    assert coordinator.media_position_updated_at == datetime(
        2026, 8, 22, 12, 0, 0, tzinfo=UTC
    )
