"""Test the Tado integration."""

import asyncio
from datetime import datetime, timedelta
import threading
import time
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from PyTado.http import Http
import pytest

from homeassistant.components.tado import DOMAIN
from homeassistant.components.tado.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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


@pytest.mark.usefixtures("init_integration")
async def test_device_via_device_links(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that child devices link to the bridge via via_device_id."""
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    bridge_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "IB1234"), config_entry.entry_id
    )
    assert bridge_device is not None

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "WR1"), config_entry.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id == bridge_device.id


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


async def test_empty_response_is_retried(
    hass: HomeAssistant,
    mock_tado_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an empty response from Tado is retried instead of raising."""
    mock_tado_api.get_me.return_value = {}
    mock_tado_api.rate_limit_info.return_value = {
        "per-day": "1000",
        "window-seconds": "86400",
        "remaining": "0",
    }
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("init_integration")
async def test_depleted_rate_limit_waits_for_reset(hass: HomeAssistant) -> None:
    """Test that a depleted rate limit backs off until the limit resets."""
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data

    with (
        patch(
            "PyTado.interface.Tado.rate_limit_info",
            return_value={"per-day": 1000, "remaining": 0},
        ),
        patch(
            "homeassistant.components.tado.coordinator.dt_util.now",
            return_value=datetime(2025, 1, 1, 7, 0, tzinfo=ZoneInfo("Europe/Berlin")),
        ),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Tado resets the budget at 12:00 Berlin time, which is five hours away.
    assert coordinator.update_interval == timedelta(hours=5)
    assert coordinator.update_interval > SCAN_INTERVAL
