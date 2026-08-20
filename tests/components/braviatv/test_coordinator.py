"""Test the BraviaTV coordinator."""

from unittest.mock import AsyncMock

from freezegun import freeze_time
import pytest

from homeassistant.components.braviatv.const import CONF_USE_PSK, DOMAIN
from homeassistant.components.braviatv.coordinator import BraviaTVCoordinator
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("start_datetime", "expected_position"),
    [
        ("2024-01-01T12:00:00", 3600),  # naive, treated as local time
        ("2024-01-01T12:00:00+02:00", 7200),  # aware
    ],
)
async def test_async_update_playing(
    hass: HomeAssistant,
    start_datetime: str,
    expected_position: int,
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

    with freeze_time("2024-01-01 12:00:00+00:00"):
        await coordinator.async_update_playing()

        assert coordinator.media_position == expected_position
        assert coordinator.media_position_updated_at == dt_util.utcnow()
