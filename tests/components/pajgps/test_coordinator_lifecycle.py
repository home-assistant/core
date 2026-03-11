"""Tests for PajGpsCoordinator lifecycle: initialisation, update behaviour, get_device_info helper, and shutdown."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pajgps_api.pajgps_api_error import AuthenticationError, PajGpsApiError
import pytest

from homeassistant.components.pajgps.coordinator import PajGpsData
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from .test_common import make_coordinator, make_device, make_trackpoint


class TestCoordinatorInit:
    """Tests for coordinator initialisation state."""


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


class TestGetDeviceInfo:
    """Tests for the get_device_info helper method."""

    def test_returns_dict_for_known_device(self):
        """Test that get_device_info returns a populated dict for a known device."""
        coord = make_coordinator()
        coord.data = PajGpsData(devices={1: make_device(1)}, positions={})
        info = coord.get_device_info(1)

        assert info is not None
        assert "identifiers" in info
        assert "name" in info
        assert info["manufacturer"] == "PAJ GPS"
        assert "model" in info

    def test_returns_none_for_unknown_device(self):
        """Test that get_device_info returns None for an unknown device ID."""
        coord = make_coordinator()
        coord.data = PajGpsData(devices={}, positions={})

        assert coord.get_device_info(999) is None

    def test_identifiers_contain_email_and_device_id(self):
        """Test that identifiers include both the email and device ID."""
        coord = make_coordinator(email="owner@example.com")
        coord.data = PajGpsData(devices={42: make_device(42)}, positions={})

        info = coord.get_device_info(42)
        identifiers = info["identifiers"]
        assert any(
            "owner@example.com" in str(i) and "42" in str(i) for i in identifiers
        )
