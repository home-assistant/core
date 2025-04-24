"""Test the Tado integration."""

import asyncio
import threading
import time
from unittest.mock import patch

from PyTado.http import Http

from homeassistant.components.tado import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_v1_migration(hass: HomeAssistant) -> None:
    """Test migration from v1 to v2 config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test",
            CONF_PASSWORD: "test",
        },
        unique_id="1",
        version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 2
    assert CONF_USERNAME not in entry.data


async def test_refresh_token_threading_lock(hass: HomeAssistant) -> None:
    """Test that threading.Lock in Http._refresh_token serializes concurrent calls."""

    timestamps: list[tuple[str, float]] = []
    lock = threading.Lock()

    def fake_refresh_token(*args, **kwargs) -> bool:
        """Simulate the refresh token process with a threading lock."""
        with lock:
            timestamps.append(("start", time.monotonic()))
            time.sleep(0.2)
            timestamps.append(("end", time.monotonic()))
            return True

    with (
        patch("PyTado.http.Http._refresh_token", side_effect=fake_refresh_token),
        patch("PyTado.http.Http.__init__", return_value=None),
    ):
        http_instance = Http()

        # Run two concurrent refresh token calls, should do the trick
        await asyncio.gather(
            hass.async_add_executor_job(http_instance._refresh_token),
            hass.async_add_executor_job(http_instance._refresh_token),
        )

    end1 = timestamps[1][1]
    start2 = timestamps[2][1]

    assert start2 >= end1, (
        f"Second refresh started before first ended: start2={start2}, end1={end1}."
    )
