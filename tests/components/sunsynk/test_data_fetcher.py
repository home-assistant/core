"""Tests for data_fetcher module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.sunsynk.const import SunSynkApiError, SunSynkAuthError
from custom_components.sunsynk.data_fetcher import (
    ErrorTracker,
    TokenManager,
    _async_fetch_successful,
    async_fetch_all_data,
    async_write_settings,
)
import pytest


class TestErrorTracker:
    """Tests for ErrorTracker."""

    def test_initial_state(self) -> None:
        """Test initial state of error tracker."""
        tracker = ErrorTracker()
        errors = tracker.as_dict()
        for cat in ("Bearer", "Events", "Updates", "Flow", "InvList", "InvParam"):
            assert errors[cat]["count"] == 0
            assert errors[cat]["payload"] == ""
            assert errors[cat]["date"] == ""

    def test_record_increments_count(self) -> None:
        """Test that recording an error increments the count."""
        tracker = ErrorTracker()
        tracker.record("Bearer", Exception("auth failed"))
        errors = tracker.as_dict()
        assert errors["Bearer"]["count"] == 1
        assert errors["Bearer"]["payload"] == "auth failed"
        assert errors["Bearer"]["date"] != ""

    def test_record_multiple(self) -> None:
        """Test recording multiple errors for the same category."""
        tracker = ErrorTracker()
        tracker.record("Events", Exception("timeout"))
        tracker.record("Events", Exception("bad response"))
        errors = tracker.as_dict()
        assert errors["Events"]["count"] == 2
        assert errors["Events"]["payload"] == "bad response"

    def test_record_unknown_category_ignored(self) -> None:
        """Test that recording an unknown category is ignored."""
        tracker = ErrorTracker()
        tracker.record("Unknown", Exception("test"))
        errors = tracker.as_dict()
        assert "Unknown" not in errors

    def test_payload_truncated_to_16_chars(self) -> None:
        """Test that error payload is truncated to 16 characters."""
        tracker = ErrorTracker()
        tracker.record("Bearer", Exception("a" * 100))
        errors = tracker.as_dict()
        assert len(errors["Bearer"]["payload"]) == 16


class TestTokenManager:
    """Tests for TokenManager."""

    @pytest.mark.asyncio
    @patch(
        "custom_components.sunsynk.data_fetcher.async_authenticate",
        new_callable=AsyncMock,
    )
    async def test_get_token_authenticates(self, mock_auth: AsyncMock) -> None:
        """Test that get_token authenticates and returns a token."""
        mock_auth.return_value = MagicMock(
            access_token="test_token",
            token_type="bearer",
            expires_in=3600,
        )
        tm = TokenManager("test@example.com", "password", 0)
        token = await tm.async_get_token()
        assert token == "test_token"
        mock_auth.assert_called_once_with("test@example.com", "password", 0, None)

    @pytest.mark.asyncio
    @patch(
        "custom_components.sunsynk.data_fetcher.async_authenticate",
        new_callable=AsyncMock,
    )
    async def test_get_token_caches(self, mock_auth: AsyncMock) -> None:
        """Test that get_token caches the token on subsequent calls."""
        mock_auth.return_value = MagicMock(
            access_token="test_token",
            token_type="bearer",
            expires_in=3600,
        )
        tm = TokenManager("test@example.com", "password", 0)
        await tm.async_get_token()
        await tm.async_get_token()
        assert mock_auth.call_count == 1


class TestWriteSettings:
    """Tests for async_write_settings."""

    @pytest.mark.asyncio
    @patch(
        "custom_components.sunsynk.data_fetcher.async_authenticate",
        new_callable=AsyncMock,
    )
    @patch("custom_components.sunsynk.data_fetcher.SunSynk")
    async def test_write_settings_calls_api(
        self,
        mock_client_cls: MagicMock,
        mock_auth: AsyncMock,
    ) -> None:
        """Test that write settings calls the API correctly."""
        mock_auth.return_value = MagicMock(
            access_token="tok",
            token_type="bearer",
            expires_in=3600,
        )
        mock_client = MagicMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.settings.write_inverter_settings_async = AsyncMock(
            return_value=MagicMock(code=0, msg="success"),
        )

        tm = TokenManager("test@example.com", "pass", 0)
        result = await async_write_settings(tm, 0, "SN123", {"cap1": "50"})

        mock_client.settings.write_inverter_settings_async.assert_called_once()
        call_kwargs = (
            mock_client.settings.write_inverter_settings_async.call_args.kwargs
        )
        assert call_kwargs["sn"] == "SN123"
        assert result["code"] == 0
        assert result["msg"] == "success"

    @pytest.mark.asyncio
    @patch(
        "custom_components.sunsynk.data_fetcher.async_authenticate",
        new_callable=AsyncMock,
    )
    @patch("custom_components.sunsynk.data_fetcher.SunSynk")
    async def test_write_settings_tracks_error(
        self,
        mock_client_cls: MagicMock,
        mock_auth: AsyncMock,
    ) -> None:
        """Test that write settings tracks errors on failure."""
        mock_auth.return_value = MagicMock(
            access_token="tok",
            token_type="bearer",
            expires_in=3600,
        )
        mock_client = MagicMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.settings.write_inverter_settings_async = AsyncMock(
            side_effect=RuntimeError("fail"),
        )

        tm = TokenManager("test@example.com", "pass", 0)
        tracker = ErrorTracker()
        with pytest.raises(RuntimeError):
            await async_write_settings(tm, 0, "SN123", {"cap1": "50"}, tracker)

        assert tracker.as_dict()["Updates"]["count"] == 1


class TestTokenManagerExpiry:
    """Tests for token expiry logic."""

    @pytest.mark.asyncio
    @patch(
        "custom_components.sunsynk.data_fetcher.async_authenticate",
        new_callable=AsyncMock,
    )
    async def test_token_refreshes_when_expired(self, mock_auth: AsyncMock) -> None:
        """Token should be re-fetched when it expires."""
        mock_auth.return_value = MagicMock(
            access_token="token1",
            token_type="bearer",
            expires_in=1,  # 1 second, less than 60s buffer
        )
        tm = TokenManager("test@example.com", "password", 0)
        await tm.async_get_token()
        # Token is already "expired" because expires_in(1) - buffer(60) < 0
        await tm.async_get_token()
        assert mock_auth.call_count == 2

    @pytest.mark.asyncio
    @patch(
        "custom_components.sunsynk.data_fetcher.async_authenticate",
        new_callable=AsyncMock,
    )
    async def test_token_auth_error_propagates(self, mock_auth: AsyncMock) -> None:
        """Auth errors should propagate from async_get_token."""
        mock_auth.side_effect = SunSynkAuthError("bad creds")
        tm = TokenManager("test@example.com", "password", 0)
        with pytest.raises(SunSynkAuthError):
            await tm.async_get_token()


class TestAsyncFetchSuccessful:
    """Tests for the _async_fetch_successful helper."""

    @pytest.mark.asyncio
    async def test_returns_data_on_success(self) -> None:
        """Test that data is returned on a successful response."""
        mock_response = MagicMock(success=True, data="result_data")

        async def coro():
            return mock_response

        result = await _async_fetch_successful(coro())
        assert result == "result_data"

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self) -> None:
        """Test that None is returned on a failed response."""
        mock_response = MagicMock(success=False)

        async def coro():
            return mock_response

        result = await _async_fetch_successful(coro())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self) -> None:
        """Test that None is returned when an exception occurs."""

        async def coro():
            raise RuntimeError("network error")

        result = await _async_fetch_successful(coro())
        assert result is None

    @pytest.mark.asyncio
    async def test_tracks_error_on_exception(self) -> None:
        """Test that errors are tracked when an exception occurs."""
        tracker = ErrorTracker()

        async def coro():
            raise RuntimeError("fail")

        await _async_fetch_successful(coro(), tracker, "Flow")
        assert tracker.as_dict()["Flow"]["count"] == 1

    @pytest.mark.asyncio
    async def test_returns_none_for_none_response(self) -> None:
        """Test that None is returned when the response is None."""

        async def coro():
            return None

        result = await _async_fetch_successful(coro())
        assert result is None


class TestAsyncFetchAllData:
    """Tests for async_fetch_all_data."""

    @pytest.mark.asyncio
    @patch(
        "custom_components.sunsynk.data_fetcher.async_authenticate",
        new_callable=AsyncMock,
    )
    @patch("custom_components.sunsynk.data_fetcher.SunSynk")
    async def test_auth_error_tracked_and_raised(
        self,
        mock_client_cls: MagicMock,
        mock_auth: AsyncMock,
    ) -> None:
        """Auth errors during fetch should be tracked and re-raised."""
        mock_auth.side_effect = SunSynkAuthError("token expired")
        tm = TokenManager("test@example.com", "pass", 0)
        tracker = ErrorTracker()

        with pytest.raises(SunSynkAuthError):
            await async_fetch_all_data(tm, 0, tracker)

        assert tracker.as_dict()["Bearer"]["count"] == 1

    @pytest.mark.asyncio
    @patch(
        "custom_components.sunsynk.data_fetcher.async_authenticate",
        new_callable=AsyncMock,
    )
    @patch("custom_components.sunsynk.data_fetcher.SunSynk")
    async def test_no_plants_raises_api_error(
        self,
        mock_client_cls: MagicMock,
        mock_auth: AsyncMock,
    ) -> None:
        """Should raise SunSynkApiError when no plants are returned."""
        mock_auth.return_value = MagicMock(
            access_token="tok",
            token_type="bearer",
            expires_in=3600,
        )
        mock_client = MagicMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.plants.get_plants_async = AsyncMock(
            return_value=MagicMock(success=False, data=None),
        )

        tm = TokenManager("test@example.com", "pass", 0)
        with pytest.raises(SunSynkApiError):
            await async_fetch_all_data(tm, 0)

    @pytest.mark.asyncio
    @patch(
        "custom_components.sunsynk.data_fetcher.async_authenticate",
        new_callable=AsyncMock,
    )
    @patch("custom_components.sunsynk.data_fetcher.SunSynk")
    async def test_plant_ignore_list(
        self,
        mock_client_cls: MagicMock,
        mock_auth: AsyncMock,
    ) -> None:
        """Plants in the ignore list should be skipped."""
        mock_auth.return_value = MagicMock(
            access_token="tok",
            token_type="bearer",
            expires_in=3600,
        )
        mock_client = MagicMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        plant1 = MagicMock(id=1, name="Plant 1")
        plant2 = MagicMock(id=2, name="Plant 2")
        mock_client.plants.get_plants_async = AsyncMock(
            return_value=MagicMock(
                success=True, data=MagicMock(infos=[plant1, plant2])
            ),
        )
        # Mock system data
        mock_client.gateways.get_gateways_async = AsyncMock(
            return_value=MagicMock(success=True, data=MagicMock(infos=[])),
        )
        mock_client.events.get_events_async = AsyncMock(
            return_value=MagicMock(success=False, data=None),
        )
        mock_client.notifications.get_messages_async = AsyncMock(
            return_value=MagicMock(success=True, data=MagicMock(infos=[])),
        )
        # Mock plant data - return empty inverter list
        mock_client.plants.get_plant_flow_async = AsyncMock(
            return_value=MagicMock(success=True, data=MagicMock()),
        )
        mock_client.inverters.get_plant_inverters_async = AsyncMock(
            return_value=MagicMock(success=True, data=MagicMock(infos=[])),
        )

        tm = TokenManager("test@example.com", "pass", 0)
        result = await async_fetch_all_data(tm, 0, plant_ignore_list={"1"})

        # Plant 1 should be ignored, only plant 2 present
        assert 1 not in result["plants"]
        assert 2 in result["plants"]
