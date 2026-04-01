"""Tests for the remote runtime."""

from __future__ import annotations

import asyncio
from pathlib import Path
import zoneinfo
from unittest.mock import AsyncMock

from hass_client.config import RemoteConfig
from hass_client.runtime import RemoteHomeAssistant
from homeassistant.util import dt as dt_util


def test_async_setup_remote_syncs_time_zone(tmp_path: Path) -> None:
    """Sync the remote timezone into hass.config and dt_util on connect."""

    async def run_test() -> None:
        original_time_zone = dt_util.get_default_time_zone()
        remote_time_zone = "Europe/Amsterdam"
        remote_api = AsyncMock()
        remote_api.async_get_config.return_value = {"time_zone": remote_time_zone}
        remote_api.subscribe_events.return_value = lambda: None

        hass = RemoteHomeAssistant(str(tmp_path))
        hass.remote_config = RemoteConfig(
            sync_states=False,
            sync_entity_registry=False,
            sync_remote_services=False,
        )
        hass.remote_api = remote_api

        try:
            await hass.async_setup_remote()

            assert hass.config.time_zone == remote_time_zone
            assert dt_util.get_default_time_zone() == zoneinfo.ZoneInfo(
                remote_time_zone
            )
            remote_api.async_get_config.assert_awaited_once()
        finally:
            dt_util.set_default_time_zone(original_time_zone)
            await hass.async_teardown_remote()

    asyncio.run(run_test())


def test_service_registry_uses_live_remote_api(tmp_path: Path) -> None:
    """Use the runtime's current remote API instead of a stale constructor copy."""

    async def run_test() -> None:
        remote_api = AsyncMock()
        remote_api.connected = True
        remote_api.async_call_service.return_value = {}

        hass = RemoteHomeAssistant(str(tmp_path))
        hass.remote_api = remote_api

        await hass.services.async_call("light", "turn_on", blocking=True)

        remote_api.async_call_service.assert_awaited_once_with(
            domain="light",
            service="turn_on",
            service_data=None,
            target=None,
            return_response=False,
        )

    asyncio.run(run_test())
