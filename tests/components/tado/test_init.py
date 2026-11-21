"""Test the Tado integration."""

import asyncio
import threading
import time
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from PyTado.http import Http
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from requests import RequestException

from homeassistant.components.tado import DOMAIN
from homeassistant.components.tado.coordinator import RATE_LIMITED_INTERVAL
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


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


@pytest.mark.usefixtures("init_integration")
async def test_rate_limit_backoff_on_exhausted_quota(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that a successful refresh with zero remaining calls backs off."""
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data

    with patch(
        "PyTado.interface.Tado.rate_limit_info",
        return_value={"per-day": 1000, "remaining": "0"},
    ):
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.update_interval >= RATE_LIMITED_INTERVAL


@pytest.mark.usefixtures("init_integration")
async def test_rate_limit_backoff_on_failed_request(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that a request failing on an exhausted quota applies the backoff."""
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data

    with (
        patch(
            "PyTado.interface.Tado.rate_limit_info",
            return_value={"per-day": 1000, "remaining": "0"},
        ),
        patch.object(
            coordinator._tado,
            "get_me",
            side_effect=RequestException("429"),
        ),
    ):
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.update_interval == RATE_LIMITED_INTERVAL
