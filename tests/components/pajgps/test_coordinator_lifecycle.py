"""Tests for PajGpsCoordinator lifecycle: initialisation, update behaviour, and shutdown."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pajgps_api.pajgps_api_error import AuthenticationError, PajGpsApiError
import pytest

from homeassistant.components.pajgps.coordinator import PajGpsData
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from .test_common import make_coordinator, make_device, make_trackpoint


class TestAsyncUpdateData:
    """Tests for the _async_update_data method."""

    @pytest.mark.asyncio
    async def test_returns_pajgps_data_with_devices_and_positions(self):
        """Test that _async_update_data returns a fully populated PajGpsData."""
        coord = make_coordinator()
        device = make_device(1)
        tp = make_trackpoint(1)
        coord.api.get_devices = AsyncMock(return_value={1: device})
        coord.api.get_all_last_positions = AsyncMock(return_value=[tp])

        result = await coord._async_update_data()

        assert isinstance(result, PajGpsData)
        assert result.devices == {1: device}
        assert result.positions == {1: tp}

    @pytest.mark.asyncio
    async def test_returns_empty_positions_when_no_devices(self):
        """Test that positions are empty when there are no devices."""
        coord = make_coordinator()
        coord.api.get_devices = AsyncMock(return_value={})

        result = await coord._async_update_data()

        assert result.devices == {}
        assert result.positions == {}

    @pytest.mark.asyncio
    async def test_get_devices_failure_raises_update_failed(self):
        """Test that a PajGpsApiError from get_devices raises UpdateFailed."""
        coord = make_coordinator()
        coord.api.get_devices = AsyncMock(side_effect=PajGpsApiError("api down"))

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_positions_failure_raises_update_failed(self):
        """Test that a PajGpsApiError from get_all_last_positions raises UpdateFailed."""
        coord = make_coordinator()
        device = make_device(1)
        coord.api.get_devices = AsyncMock(return_value={1: device})
        coord.api.get_all_last_positions = AsyncMock(
            side_effect=PajGpsApiError("positions api down")
        )

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()


class TestAsyncSetup:
    """Tests for the _async_setup method (runs once before the first refresh)."""

    @pytest.mark.asyncio
    async def test_login_failure_raises_config_entry_auth_failed(self):
        """Test that an authentication error during login raises ConfigEntryAuthFailed."""
        coord = make_coordinator()
        coord.api.login = AsyncMock(side_effect=AuthenticationError("bad creds"))

        with pytest.raises(ConfigEntryAuthFailed):
            await coord._async_setup()

    @pytest.mark.asyncio
    async def test_generic_login_exception_raises_config_entry_not_ready(self):
        """A non-auth exception during login must raise ConfigEntryNotReady."""
        coord = make_coordinator()
        coord.api.login = AsyncMock(side_effect=ConnectionError("network gone"))

        with pytest.raises(ConfigEntryNotReady):
            await coord._async_setup()
