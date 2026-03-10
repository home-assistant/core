"""Tests for PajGpsCoordinator lifecycle: initialisation, tier scheduling, initial refresh flow, get_device_info helper, and shutdown."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

from pajgps_api.pajgps_api_error import AuthenticationError
import pytest

from homeassistant.components.pajgps.coordinator import PajGpsCoordinator, PajGpsData
from homeassistant.helpers.update_coordinator import UpdateFailed

from .test_common import make_coordinator, make_device


class TestCoordinatorInit:
    """Tests for coordinator initialisation state."""

    def test_initial_snapshot_is_empty(self):
        """Test that the initial data snapshot is an empty PajGpsData."""
        coord = make_coordinator()
        assert isinstance(coord.data, PajGpsData)
        assert coord.data.devices == []

    def test_tier_timestamps_start_at_zero(self):
        """Test that all tier fetch timestamps are initialised to zero."""
        coord = make_coordinator()
        assert coord._last_devices_fetch == 0.0
        assert coord._last_positions_fetch == 0.0

    def test_initial_refresh_done_is_false(self):
        """Test that the initial refresh flag starts as False."""
        coord = make_coordinator()
        assert not coord._initial_refresh_done


class TestTierScheduling:
    """Tests for tier-based scheduling logic in the coordinator."""

    async def _make_ready_coordinator(self, **entry_kwargs) -> PajGpsCoordinator:
        """Return a coordinator whose initial refresh is already done."""
        coord = make_coordinator(**entry_kwargs)
        coord._initial_refresh_done = True
        coord.data = PajGpsData(devices=[make_device(1)])
        return coord

    @pytest.mark.asyncio
    async def test_devices_tier_triggered_when_overdue(self):
        """Test that the devices tier is triggered when the fetch is overdue."""
        coord = await self._make_ready_coordinator()
        coord._last_devices_fetch = 0.0  # very overdue

        with patch.object(
            coord, "_run_devices_tier", new_callable=AsyncMock
        ) as mock_tier:
            coord.hass.async_create_task = asyncio.ensure_future
            await coord._async_update_data()
            await asyncio.sleep(0.05)
            mock_tier.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_devices_tier_not_triggered_when_fresh(self):
        """Test that the devices tier is not triggered when the fetch is recent."""
        coord = await self._make_ready_coordinator()
        coord._last_devices_fetch = time.monotonic()  # just fetched

        with patch.object(
            coord, "_run_devices_tier", new_callable=AsyncMock
        ) as mock_tier:
            coord.hass.async_create_task = asyncio.ensure_future
            await coord._async_update_data()
            await asyncio.sleep(0.05)
            mock_tier.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_current_snapshot_on_subsequent_calls(self):
        """Test that subsequent calls return the current data snapshot."""
        coord = await self._make_ready_coordinator()
        coord._last_devices_fetch = time.monotonic()
        coord._last_positions_fetch = time.monotonic()
        coord._last_notifications_fetch = time.monotonic()

        result = await coord._async_update_data()
        assert result is coord.data

    @pytest.mark.asyncio
    async def test_login_failure_raises_update_failed(self):
        """Test that an authentication error during login raises UpdateFailed."""
        coord = make_coordinator()
        coord.api.login = AsyncMock(side_effect=AuthenticationError("bad creds"))

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_generic_login_exception_raises_update_failed(self):
        """A non-auth exception during login must also raise UpdateFailed (line 125-126)."""
        coord = make_coordinator()
        coord.api.login = AsyncMock(side_effect=ConnectionError("network gone"))

        with pytest.raises(UpdateFailed) as ctx:
            await coord._async_update_data()

        assert "connection error" in str(ctx.value).lower()


class TestInitialRefresh:
    """Tests for the initial refresh flow that runs all three data tiers."""

    @pytest.mark.asyncio
    async def test_initial_refresh_runs_all_three_tiers(self):
        """Test that the initial refresh awaits all three data tiers."""
        coord = make_coordinator()

        with (
            patch.object(coord, "_run_devices_tier", new_callable=AsyncMock) as d,
            patch.object(coord, "_run_positions_tier", new_callable=AsyncMock) as p,
        ):
            await coord._async_update_data()
            d.assert_awaited_once()
            p.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initial_refresh_sets_flag(self):
        """Test that the initial refresh sets the _initial_refresh_done flag."""
        coord = make_coordinator()

        with (
            patch.object(coord, "_run_devices_tier", new_callable=AsyncMock),
            patch.object(coord, "_run_positions_tier", new_callable=AsyncMock),
        ):
            await coord._async_update_data()
            assert coord._initial_refresh_done

    @pytest.mark.asyncio
    async def test_initial_refresh_returns_data(self):
        """Test that the initial refresh returns a PajGpsData instance."""
        coord = make_coordinator()
        coord.data = PajGpsData(devices=[make_device(1)])

        with (
            patch.object(coord, "_run_devices_tier", new_callable=AsyncMock),
            patch.object(coord, "_run_positions_tier", new_callable=AsyncMock),
        ):
            result = await coord._async_update_data()
            assert isinstance(result, PajGpsData)


class TestGetDeviceInfo:
    """Tests for the get_device_info helper method."""

    def test_returns_dict_for_known_device(self):
        """Test that get_device_info returns a populated dict for a known device."""
        coord = make_coordinator()
        coord.data = PajGpsData(devices=[make_device(1)])
        info = coord.get_device_info(1)

        assert info is not None
        assert "identifiers" in info
        assert "name" in info
        assert info["manufacturer"] == "PAJ GPS"
        assert "model" in info

    def test_returns_none_for_unknown_device(self):
        """Test that get_device_info returns None for an unknown device ID."""
        coord = make_coordinator()
        coord.data = PajGpsData(devices=[])

        assert coord.get_device_info(999) is None

    def test_identifiers_contain_guid_and_device_id(self):
        """Test that identifiers include both the GUID and device ID."""
        coord = make_coordinator(guid="my-guid")
        coord.data = PajGpsData(devices=[make_device(42)])

        info = coord.get_device_info(42)
        identifiers = info["identifiers"]
        assert any("my-guid" in str(i) and "42" in str(i) for i in identifiers)


class TestShutdown:
    """Tests for coordinator shutdown and cleanup behaviour."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_api(self):
        """Test that shutdown awaits the API close method."""
        coord = make_coordinator()
        coord.api.close = AsyncMock()

        await coord.async_shutdown()

        coord.api.close.assert_awaited_once()
