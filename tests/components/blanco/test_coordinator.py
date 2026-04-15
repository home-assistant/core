"""Tests for coordinator.py — BlancoDataUpdateCoordinator and helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from blanco_smart_home_api_client import (
    BlancoActionType,
    BlancoApiClient,
    BlancoWaterType,
)
from blanco_smart_home_api_client.mask import mask_dev_id, mask_headers
from blanco_smart_home_api_client.results import StatTotalItem
import pytest

from homeassistant.components.blanco.const import (
    CONF_BACKFILL_DONE,
    CONF_LAST_ACTION_TS,
)
from homeassistant.components.blanco.coordinator import (
    _ACTIONS_504_LIMIT,
    _compute_stats_ranges,
    _extract_stat_water_l,
    _stat_id_part,
)
from homeassistant.components.blanco.definitions import (
    BlancoDeviceType,
    BlancoTimeRange,
)
from homeassistant.config_entries import ConfigEntryAuthFailed

from .conftest import make_coordinator, make_get_response, make_mock_entry

# ── Sample API response payloads ───────────────────────────────────────────────

SYSTEM_RESPONSE = {
    "results": [{"dev_name": "My BLANCO", "sw_ver_comm_con": "1.0"}],
    "info": {"connected": True, "online": 1700000000000, "dev_type": 2},
}
STATUS_RESPONSE = {
    "results": [{"co2_rest": 75, "filter_rest": 50}],
    "info": {},
}
SETTINGS_RESPONSE = {
    "results": [{"set_point_cooling": 8, "set_point_heating": 85}],
    "info": {},
}
ERRORS_RESPONSE = {"results": [], "info": {}}
ACTIONS_RESPONSE = {"results": [], "info": {}}


# ── mask_headers ──────────────────────────────────────────────────────────────


class TestMaskHeaders:
    """Tests for the mask_headers helper."""

    def test_authorization_longer_than_20_chars_is_truncated(self) -> None:
        """Values longer than 20 chars for Authorization are truncated to 20 + '...'."""
        headers = {"Authorization": "Bearer averylongtokenthatexceedslimit"}
        result = mask_headers(headers)
        assert result["Authorization"] == "Bearer averylongtoke..."
        assert len(result["Authorization"]) == 23  # 20 + len("...")

    def test_x_api_key_longer_than_20_chars_is_truncated(self) -> None:
        """Values longer than 20 chars for X-Api-Key are truncated."""
        headers = {"X-Api-Key": "averylongapikeyvalue12345"}
        result = mask_headers(headers)
        assert result["X-Api-Key"] == "averylongapikeyvalue..."

    def test_x_app_id_longer_than_20_chars_is_truncated(self) -> None:
        """Values longer than 20 chars for X-App-Id are truncated."""
        headers = {"X-App-Id": "app-id-that-is-way-too-long-for-display"}
        result = mask_headers(headers)
        assert result["X-App-Id"] == "app-id-that-is-way-t..."

    def test_sensitive_value_exactly_20_chars_is_unchanged(self) -> None:
        """Sensitive values of exactly 20 chars are returned unchanged."""
        headers = {"Authorization": "exactly20charsvalue!"}
        assert len(headers["Authorization"]) == 20
        result = mask_headers(headers)
        assert result["Authorization"] == "exactly20charsvalue!"

    def test_sensitive_value_shorter_than_20_chars_is_unchanged(self) -> None:
        """Sensitive values shorter than 20 chars are returned unchanged."""
        headers = {"X-Api-Key": "shortkey"}
        result = mask_headers(headers)
        assert result["X-Api-Key"] == "shortkey"

    def test_non_sensitive_key_is_unchanged(self) -> None:
        """Non-sensitive header values are never modified."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        result = mask_headers(headers)
        assert result == headers

    def test_mixed_headers(self) -> None:
        """Only sensitive keys are truncated when headers contain a mix."""
        headers = {
            "Authorization": "Bearer averylongtokenthatexceedslimit",
            "Content-Type": "application/json",
        }
        result = mask_headers(headers)
        assert result["Authorization"].endswith("...")
        assert result["Content-Type"] == "application/json"


# ── _static_headers ───────────────────────────────────────────────────────────


class TestStaticHeaders:
    """Tests for the _static_headers instance variable of BlancoApiClient.

    _STATIC_HEADERS is no longer a module-level constant — it is built per
    BlancoApiClient instance from the constructor parameters app_version,
    app_build, and os_version.  Tests verify both the fixed values (User-Agent,
    X-OS-Type) and that constructor arguments flow through correctly.
    """

    def test_static_headers_keys_present(self, mock_hass: MagicMock) -> None:
        """_static_headers must define all required standard keys."""
        coord = make_coordinator(mock_hass)
        headers = coord._api._static_headers
        assert "User-Agent" in headers
        assert "X-App-Version" in headers
        assert "X-App-Build" in headers
        assert "X-OS-Type" in headers
        assert "X-OS-Version" in headers

    def test_user_agent_value(self, mock_hass: MagicMock) -> None:
        """User-Agent must be the fixed identifier string 'ha-blanco'."""
        coord = make_coordinator(mock_hass)
        assert coord._api._static_headers["User-Agent"] == "ha-blanco"

    def test_os_type_value(self, mock_hass: MagicMock) -> None:
        """X-OS-Type must always be 'HomeAssistant'."""
        coord = make_coordinator(mock_hass)
        assert coord._api._static_headers["X-OS-Type"] == "HomeAssistant"

    def test_app_version_passed_to_static_headers(self) -> None:
        """app_version passed to BlancoApiClient must appear in X-App-Version."""
        client = BlancoApiClient(MagicMock(), app_version="9.9.9", app_build="42")
        assert client._static_headers["X-App-Version"] == "9.9.9"

    def test_app_build_passed_to_static_headers(self) -> None:
        """app_build passed to BlancoApiClient must appear in X-App-Build."""
        client = BlancoApiClient(MagicMock(), app_version="9.9.9", app_build="42")
        assert client._static_headers["X-App-Build"] == "42"

    def test_os_version_passed_to_static_headers(self) -> None:
        """os_version passed to BlancoApiClient must appear in X-OS-Version."""
        client = BlancoApiClient(MagicMock(), os_version="2026.1.0")
        assert client._static_headers["X-OS-Version"] == "2026.1.0"

    def test_api_client_auth_headers_include_static_headers(
        self, mock_hass: MagicMock
    ) -> None:
        """API client auth headers must contain all _static_headers keys and values."""
        coord = make_coordinator(mock_hass)
        auth_headers = coord._api._auth_headers()
        for key, value in coord._api._static_headers.items():
            assert auth_headers.get(key) == value, (
                f"Expected _auth_headers()[{key!r}] == {value!r}, "
                f"got {auth_headers.get(key)!r}"
            )

    @pytest.mark.asyncio
    async def test_renewal_request_includes_static_headers(
        self, mock_hass: MagicMock
    ) -> None:
        """The token-renewal POST must include all _static_headers."""
        renewal_body = {
            "results": [{"token": "new-token", "token_type": "Bearer"}],
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=renewal_body)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post.return_value = cm

        coord = make_coordinator(mock_hass, session=mock_session)
        await coord._async_renew_token()

        _, call_kwargs = mock_session.post.call_args
        sent_headers: dict[str, str] = call_kwargs.get("headers", {})
        for key, value in coord._api._static_headers.items():
            assert sent_headers.get(key) == value, (
                f"Renewal POST missing header {key!r}={value!r}"
            )


# ── mask_dev_id ───────────────────────────────────────────────────────────────


class TestMaskDevId:
    """Tests for the mask_dev_id helper."""

    def test_longer_than_8_chars_shows_first_8_plus_ellipsis(self) -> None:
        """Values longer than 8 chars expose only the first 8 chars."""
        result = mask_dev_id("abc123devid")
        assert result == "abc123de..."

    def test_exactly_8_chars_unchanged(self) -> None:
        """A value of exactly 8 chars is returned unchanged."""
        result = mask_dev_id("12345678")
        assert result == "12345678"

    def test_shorter_than_8_chars_unchanged(self) -> None:
        """A value shorter than 8 chars is returned unchanged."""
        result = mask_dev_id("abc")
        assert result == "abc"

    def test_none_returns_empty_string(self) -> None:
        """None input returns an empty string."""
        assert mask_dev_id(None) == ""

    def test_empty_string_returns_empty_string(self) -> None:
        """An empty string input returns an empty string."""
        assert mask_dev_id("") == ""


# ── _stat_id_part ──────────────────────────────────────────────────────────────


class TestStatIdPart:
    """Tests for the _stat_id_part helper."""

    def test_alphanumeric_input_is_lowercased(self) -> None:
        """Pure alphanumeric input is returned lowercased and unchanged."""
        assert _stat_id_part("ABC123") == "abc123"

    def test_hyphens_become_underscores(self) -> None:
        """Hyphens are replaced by underscores."""
        assert _stat_id_part("my-device") == "my_device"

    def test_consecutive_special_chars_become_single_underscore(self) -> None:
        """A run of consecutive non-alphanumeric chars collapses to one underscore."""
        assert _stat_id_part("my--device__id") == "my_device_id"

    def test_leading_and_trailing_underscores_stripped(self) -> None:
        """Leading and trailing underscores are stripped from the result."""
        assert _stat_id_part("--device--") == "device"

    def test_entirely_special_chars_falls_back_to_device(self) -> None:
        """Input that results in an empty string after sanitisation returns 'device'."""
        assert _stat_id_part("---") == "device"

    def test_empty_string_falls_back_to_device(self) -> None:
        """An empty input string returns 'device'."""
        assert _stat_id_part("") == "device"

    def test_mixed_valid_and_special_chars(self) -> None:
        """Mixed input with valid and special chars is correctly sanitised."""
        assert _stat_id_part("Hello World!") == "hello_world"


# ── _update_water_totals ───────────────────────────────────────────────────────


class TestUpdateWaterTotals:
    """Tests for BlancoDataUpdateCoordinator._update_water_totals."""

    def _make_action(
        self,
        evt_ts: int,
        amt: int,
        tap: BlancoWaterType = BlancoWaterType.STILL,
    ) -> dict:
        """Build a minimal normalised action dict."""
        return {
            "act_type": BlancoActionType.WATER_DISPENSE,
            "evt_ts": evt_ts,
            "tap_state": tap,
            "disp_wtr_amt": amt,
        }

    def test_accumulates_all_and_per_type_buckets(self, mock_hass: MagicMock) -> None:
        """Water totals for all, still, medium, and classic are accumulated correctly."""
        coord = make_coordinator(mock_hass)
        actions = [
            self._make_action(1700000001000, 250, BlancoWaterType.STILL),
            self._make_action(1700000002000, 300, BlancoWaterType.MEDIUM),
            self._make_action(1700000003000, 150, BlancoWaterType.CLASSIC),
        ]
        coord._update_water_totals(actions)
        assert coord._water_totals_ml["all"] == 700
        assert coord._water_totals_ml["still"] == 250
        assert coord._water_totals_ml["medium"] == 300
        assert coord._water_totals_ml["classic"] == 150

    def test_events_at_or_before_last_action_ts_are_skipped(
        self, mock_hass: MagicMock
    ) -> None:
        """Events with evt_ts <= _last_action_ts are skipped (deduplication)."""
        coord = make_coordinator(mock_hass)
        coord._last_action_ts = 1700000002000
        actions = [
            self._make_action(1700000001000, 500, BlancoWaterType.STILL),  # old — skip
            self._make_action(
                1700000002000, 500, BlancoWaterType.STILL
            ),  # equal — skip
            self._make_action(
                1700000003000, 200, BlancoWaterType.STILL
            ),  # new — include
        ]
        coord._update_water_totals(actions)
        assert coord._water_totals_ml["all"] == 200
        assert coord._water_totals_ml["still"] == 200

    def test_last_action_ts_advances_to_highest_evt_ts(
        self, mock_hass: MagicMock
    ) -> None:
        """_last_action_ts is updated to the highest evt_ts in the new events."""
        coord = make_coordinator(mock_hass)
        actions = [
            self._make_action(1700000001000, 100, BlancoWaterType.STILL),
            self._make_action(1700000005000, 200, BlancoWaterType.STILL),
            self._make_action(1700000003000, 150, BlancoWaterType.STILL),
        ]
        coord._update_water_totals(actions)
        assert coord._last_action_ts == 1700000005000

    def test_hot_water_accumulated_for_aio(self, mock_hass: MagicMock) -> None:
        """Hot water events are accumulated into the hot bucket."""
        coord = make_coordinator(mock_hass, dev_type=BlancoDeviceType.AIO)
        # AIO coordinator starts with hot=0; manually add it to the totals
        coord._water_totals_ml["hot"] = 0
        actions = [self._make_action(1700000001000, 100, BlancoWaterType.HOT)]
        coord._update_water_totals(actions)
        assert coord._water_totals_ml["hot"] == 100
        assert coord._water_totals_ml["all"] == 100


# ── _async_update_data ─────────────────────────────────────────────────────────


class TestAsyncUpdateData:
    """Async integration tests for BlancoDataUpdateCoordinator._async_update_data."""

    def _make_session(self, *responses: MagicMock) -> MagicMock:
        """Return a mock aiohttp session whose .get() yields *responses* in order.

        Configures a default 404 POST response for the /stats endpoint so that
        tests which only care about GET endpoints do not fail on the stats call.
        """
        session = MagicMock()
        session.get.side_effect = list(responses)
        # Configure a default stats POST mock (404 → stats remain None).
        default_stats_resp = AsyncMock()
        default_stats_resp.status = 404
        default_stats_resp.json = AsyncMock(return_value={})
        default_stats_cm = MagicMock()
        default_stats_cm.__aenter__ = AsyncMock(return_value=default_stats_resp)
        default_stats_cm.__aexit__ = AsyncMock(return_value=False)
        session.post.return_value = default_stats_cm
        return session

    def _make_stats_post_response(
        self, status: int, json_data: dict | None = None
    ) -> MagicMock:
        """Return an async context-manager mock for a /stats POST response."""
        resp = AsyncMock()
        resp.status = status
        resp.json = AsyncMock(return_value=json_data or {})
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    @pytest.mark.asyncio
    async def test_all_endpoints_200_returns_structured_data(
        self, mock_hass: MagicMock
    ) -> None:
        """All five endpoints returning 200 produces a correctly structured data dict."""
        # BACKFILL_DONE=True so only one /actions GET is issued.
        session = self._make_session(
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(200, STATUS_RESPONSE),
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
            make_get_response(200, ACTIONS_RESPONSE),
        )
        coord = make_coordinator(mock_hass, session=session)
        data = await coord._async_update_data()

        assert "system" in data
        assert "status" in data
        assert "settings" in data
        assert "errors" in data
        assert "actions" in data
        assert "stats" in data
        assert data["system"]["params"]["dev_name"] == "My BLANCO"
        assert data["status"]["params"]["co2_rest"] == 75
        assert data["settings"]["params"]["set_point_cooling"] == 8
        assert data["errors"]["errors"] == []
        assert "totals" in data["actions"]

    @pytest.mark.asyncio
    async def test_one_endpoint_500_uses_previous_data_for_that_key(
        self, mock_hass: MagicMock
    ) -> None:
        """A 500 on /status falls back to previous coordinator data for that key."""
        session = self._make_session(
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(500, {}),  # /status fails
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
            make_get_response(200, ACTIONS_RESPONSE),
        )
        coord = make_coordinator(mock_hass, session=session)
        # Seed previous data so the fallback has something to return.
        coord.data = {
            "system": {"params": {}, "info": {}},
            "status": {"params": {"co2_rest": 99}, "info": {}},
            "settings": {"params": {}, "info": {}},
            "errors": {"errors": [], "info": {}},
            "actions": {"actions": [], "info": {}, "totals": {}},
        }
        data = await coord._async_update_data()

        # The previous status data is used as fallback.
        assert data["status"]["params"]["co2_rest"] == 99
        # Other endpoints still return fresh data.
        assert data["system"]["params"]["dev_name"] == "My BLANCO"

    @pytest.mark.asyncio
    async def test_401_with_successful_renewal_retries_and_succeeds(
        self, mock_hass: MagicMock
    ) -> None:
        """A 401 on /system triggers renewal; success causes the request to be retried."""
        session = self._make_session(
            make_get_response(401, {}),  # /system — expired token
            make_get_response(200, SYSTEM_RESPONSE),  # /system — retry after renewal
            make_get_response(200, STATUS_RESPONSE),
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
            make_get_response(200, ACTIONS_RESPONSE),
        )
        coord = make_coordinator(mock_hass, session=session)
        with patch.object(coord, "_async_renew_token", AsyncMock(return_value=True)):
            data = await coord._async_update_data()

        assert data["system"]["params"]["dev_name"] == "My BLANCO"

    @pytest.mark.asyncio
    async def test_401_with_failed_renewal_raises_config_entry_auth_failed(
        self, mock_hass: MagicMock
    ) -> None:
        """A 401 on /system where renewal also fails raises ConfigEntryAuthFailed."""
        session = self._make_session(
            make_get_response(401, {}),  # /system — expired token, no retry
        )
        coord = make_coordinator(mock_hass, session=session)
        with (
            patch.object(coord, "_async_renew_token", AsyncMock(return_value=False)),
            pytest.raises(ConfigEntryAuthFailed),
        ):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_stats_data_none_for_non_stats_device_type(
        self, mock_hass: MagicMock
    ) -> None:
        """Stats totals remain None when dev_type has no /stats water parameter."""
        session = self._make_session(
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(200, STATUS_RESPONSE),
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
            make_get_response(200, ACTIONS_RESPONSE),
        )
        coord = make_coordinator(
            mock_hass, session=session, dev_type=BlancoDeviceType.SODA2
        )
        data = await coord._async_update_data()

        assert "stats" in data
        totals = data["stats"]["totals"]
        assert totals["today"] is None
        assert totals["week"] is None
        assert totals["month"] is None
        assert totals["year"] is None

    @pytest.mark.asyncio
    async def test_stats_totals_populated_from_200_response(
        self, mock_hass: MagicMock
    ) -> None:
        """Stats totals are extracted from a 200 /stats response for AIO device."""
        stats_body = {
            "results": [
                {
                    "range": {},
                    "total": [
                        {"par": "disp_wtr_amt", "cnt": 5, "func": 0, "val": 2500}
                    ],
                    "details": [],
                },
                {
                    "range": {},
                    "total": [
                        {"par": "disp_wtr_amt", "cnt": 20, "func": 0, "val": 15000}
                    ],
                    "details": [],
                },
                {
                    "range": {},
                    "total": [
                        {"par": "disp_wtr_amt", "cnt": 80, "func": 0, "val": 60000}
                    ],
                    "details": [],
                },
                {
                    "range": {},
                    "total": [
                        {"par": "disp_wtr_amt", "cnt": 300, "func": 0, "val": 250000}
                    ],
                    "details": [],
                },
            ],
            "info": {},
        }
        session = self._make_session(
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(200, STATUS_RESPONSE),
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
            make_get_response(200, ACTIONS_RESPONSE),
        )
        session.post.return_value = self._make_stats_post_response(200, stats_body)
        coord = make_coordinator(mock_hass, session=session)
        data = await coord._async_update_data()

        assert data["stats"]["totals"]["today"] == pytest.approx(2.5)
        assert data["stats"]["totals"]["week"] == pytest.approx(15.0)
        assert data["stats"]["totals"]["month"] == pytest.approx(60.0)
        assert data["stats"]["totals"]["year"] == pytest.approx(250.0)

    @pytest.mark.asyncio
    async def test_stats_totals_remain_none_on_non_200_stats_response(
        self, mock_hass: MagicMock
    ) -> None:
        """Stats totals remain None when the /stats endpoint returns a non-200 status."""
        session = self._make_session(
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(200, STATUS_RESPONSE),
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
            make_get_response(200, ACTIONS_RESPONSE),
        )
        session.post.return_value = self._make_stats_post_response(503)
        coord = make_coordinator(mock_hass, session=session)
        data = await coord._async_update_data()

        totals = data["stats"]["totals"]
        assert totals["today"] is None
        assert totals["week"] is None
        assert totals["month"] is None
        assert totals["year"] is None


# ── _async_renew_token ─────────────────────────────────────────────────────────


class TestAsyncRenewToken:
    """Async tests for BlancoDataUpdateCoordinator._async_renew_token."""

    @pytest.mark.asyncio
    async def test_successful_post_returns_true_and_updates_auth_header(
        self, mock_hass: MagicMock
    ) -> None:
        """A 200 renewal response returns True and updates the Authorization header."""
        renewal_body = {
            "results": [{"token": "new-token-value", "token_type": "Bearer"}],
            "errors": None,
            "info": None,
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=renewal_body)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post.return_value = cm

        coord = make_coordinator(mock_hass, session=mock_session)
        result = await coord._async_renew_token()

        assert result is True
        assert coord._api._auth_headers()["Authorization"] == "Bearer new-token-value"

    @pytest.mark.asyncio
    async def test_non_200_post_returns_false(self, mock_hass: MagicMock) -> None:
        """A non-200 renewal response returns False."""
        mock_resp = AsyncMock()
        mock_resp.status = 401
        mock_resp.json = AsyncMock(return_value={"results": []})
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post.return_value = cm

        coord = make_coordinator(mock_hass, session=mock_session)
        result = await coord._async_renew_token()

        assert result is False


# ── Actions 504 handling ───────────────────────────────────────────────────────

# Fixed timestamp injected when datetime.now() is patched in 504 tests.
_FIXED_NOW_S: float = 1_700_100_000.0
_FIXED_NOW_MS: int = int(_FIXED_NOW_S * 1000)
# Real datetime equivalent of _FIXED_NOW_S — used to replace MagicMock returns
# in datetime.now() patches so that _compute_stats_ranges receives a proper object.
_FIXED_NOW_DT: datetime = datetime.fromtimestamp(_FIXED_NOW_S, tz=UTC)


class TestActions504Handling:
    """Tests for the consecutive HTTP 504 counter on the /actions endpoint."""

    def _make_all_ok_except_actions(self, actions_status: int) -> list[MagicMock]:
        """Return five mock GET responses where /actions returns *actions_status*."""
        return [
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(200, STATUS_RESPONSE),
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
            make_get_response(actions_status, {}),
        ]

    @staticmethod
    def _make_default_stats_post_cm() -> MagicMock:
        """Return a 404 async context-manager mock for the /stats POST endpoint.

        Used to configure session.post on bare MagicMock sessions so that the
        stats block in _async_update_data() does not raise TypeError.
        """
        resp = AsyncMock()
        resp.status = 404
        resp.json = AsyncMock(return_value={})
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    @pytest.mark.asyncio
    async def test_below_limit_504s_do_not_advance_ts(
        self, mock_hass: MagicMock
    ) -> None:
        """504 responses below the limit leave _last_action_ts unchanged.

        Skipped when _ACTIONS_504_LIMIT is 1 because every 504 immediately
        reaches the limit and there are no below-limit responses to test.
        """
        if _ACTIONS_504_LIMIT <= 1:
            pytest.skip("No below-limit 504 responses when limit is 1")
        session = MagicMock()
        session.get.side_effect = self._make_all_ok_except_actions(504)
        coord = make_coordinator(mock_hass, session=session)
        initial_ts = coord._last_action_ts

        await coord._async_update_data()

        assert coord._actions_504_count == 1
        assert coord._last_action_ts == initial_ts

    @pytest.mark.asyncio
    async def test_two_consecutive_504s_do_not_advance_ts(
        self, mock_hass: MagicMock
    ) -> None:
        """Two consecutive 504 responses leave _last_action_ts unchanged."""
        coord = make_coordinator(mock_hass)
        initial_ts = coord._last_action_ts

        for _ in range(_ACTIONS_504_LIMIT - 1):
            session = MagicMock()
            session.get.side_effect = self._make_all_ok_except_actions(504)
            coord._api._session = session
            await coord._async_update_data()

        assert coord._actions_504_count == _ACTIONS_504_LIMIT - 1
        assert coord._last_action_ts == initial_ts

    @pytest.mark.asyncio
    async def test_three_consecutive_504s_advance_last_action_ts(
        self, mock_hass: MagicMock
    ) -> None:
        """Three consecutive 504 responses advance _last_action_ts to the fixed now."""
        coord = make_coordinator(mock_hass)

        with patch("homeassistant.components.blanco.coordinator.datetime") as mock_dt:
            # Use a real datetime so _compute_stats_ranges receives a proper object.
            mock_dt.now.return_value = _FIXED_NOW_DT
            for _ in range(_ACTIONS_504_LIMIT):
                session = MagicMock()
                session.get.side_effect = self._make_all_ok_except_actions(504)
                session.post.return_value = self._make_default_stats_post_cm()
                coord._api._session = session
                await coord._async_update_data()

        assert coord._last_action_ts == _FIXED_NOW_MS

    @pytest.mark.asyncio
    async def test_counter_resets_to_zero_after_reaching_limit(
        self, mock_hass: MagicMock
    ) -> None:
        """After the limit is reached the counter is reset to 0."""
        coord = make_coordinator(mock_hass)

        with patch("homeassistant.components.blanco.coordinator.datetime") as mock_dt:
            # Use a real datetime so _compute_stats_ranges receives a proper object.
            mock_dt.now.return_value = _FIXED_NOW_DT
            for _ in range(_ACTIONS_504_LIMIT):
                session = MagicMock()
                session.get.side_effect = self._make_all_ok_except_actions(504)
                session.post.return_value = self._make_default_stats_post_cm()
                coord._api._session = session
                await coord._async_update_data()

        assert coord._actions_504_count == 0

    @pytest.mark.asyncio
    async def test_counter_resets_to_zero_after_successful_actions_response(
        self, mock_hass: MagicMock
    ) -> None:
        """A successful /actions response resets the counter to 0."""
        coord = make_coordinator(mock_hass)

        # Accumulate 504s up to just below the limit.
        # When limit == 1 there are no below-limit 504s, so the loop is
        # skipped and the counter is already 0 — the postcondition still holds.
        for _ in range(_ACTIONS_504_LIMIT - 1):
            session = MagicMock()
            session.get.side_effect = self._make_all_ok_except_actions(504)
            session.post.return_value = self._make_default_stats_post_cm()
            coord._api._session = session
            await coord._async_update_data()

        assert coord._actions_504_count == _ACTIONS_504_LIMIT - 1

        # One successful poll resets the counter.
        session = MagicMock()
        session.get.side_effect = [
            make_get_response(200, SYSTEM_RESPONSE),
            make_get_response(200, STATUS_RESPONSE),
            make_get_response(200, SETTINGS_RESPONSE),
            make_get_response(200, ERRORS_RESPONSE),
            make_get_response(200, ACTIONS_RESPONSE),
        ]
        session.post.return_value = self._make_default_stats_post_cm()
        coord._api._session = session
        await coord._async_update_data()

        assert coord._actions_504_count == 0

    @pytest.mark.asyncio
    async def test_non_504_error_does_not_increment_counter(
        self, mock_hass: MagicMock
    ) -> None:
        """A non-504 failure (e.g. 500) does not change the 504 counter."""
        session = MagicMock()
        session.get.side_effect = self._make_all_ok_except_actions(500)
        session.post.return_value = self._make_default_stats_post_cm()
        coord = make_coordinator(mock_hass, session=session)

        await coord._async_update_data()

        assert coord._actions_504_count == 0

    @pytest.mark.asyncio
    async def test_backfill_504_limit_persists_backfill_done_and_ts(
        self, mock_hass: MagicMock
    ) -> None:
        """504 limit during backfill persists CONF_BACKFILL_DONE and CONF_LAST_ACTION_TS.

        The next poll must enter the incremental path with from=now_ts.
        Without the async_update_entry call the next poll would restart
        the backfill from from=0.
        """
        entry = make_mock_entry(
            data={CONF_BACKFILL_DONE: False, CONF_LAST_ACTION_TS: 0}
        )
        coord = make_coordinator(mock_hass, entry=entry)

        with patch("homeassistant.components.blanco.coordinator.datetime") as mock_dt:
            # Use a real datetime so _compute_stats_ranges receives a proper object.
            mock_dt.now.return_value = _FIXED_NOW_DT
            for _ in range(_ACTIONS_504_LIMIT):
                session = MagicMock()
                session.get.side_effect = self._make_all_ok_except_actions(504)
                session.post.return_value = self._make_default_stats_post_cm()
                coord._api._session = session
                await coord._async_update_data()

        # async_update_entry must have been called with the advanced ts and
        # backfill flag so the next poll enters the incremental path.
        update_calls = mock_hass.config_entries.async_update_entry.call_args_list
        last_backfill_call = next(
            (
                call.kwargs["data"]
                for call in reversed(update_calls)
                if "data" in call.kwargs and CONF_BACKFILL_DONE in call.kwargs["data"]
            ),
            None,
        )
        assert last_backfill_call is not None, (
            "async_update_entry was never called with CONF_BACKFILL_DONE"
        )
        assert last_backfill_call[CONF_BACKFILL_DONE] is True
        assert last_backfill_call[CONF_LAST_ACTION_TS] == _FIXED_NOW_MS
        assert coord._last_action_ts == _FIXED_NOW_MS
        assert coord._actions_504_count == 0


# ── _compute_stats_ranges ──────────────────────────────────────────────────────


class TestComputeStatsRanges:
    """Tests for the _compute_stats_ranges helper."""

    def _now(self, year: int, month: int, day: int, hour: int, minute: int) -> datetime:
        """Return a UTC datetime for the given components."""
        return datetime(year, month, day, hour, minute, 0, tzinfo=UTC)

    def test_today_start_is_local_midnight(self) -> None:
        """The first range starts at local midnight of the current day."""
        # 2024-03-15 10:30 UTC = 2024-03-15 11:30 CET (UTC+1)
        now_utc = self._now(2024, 3, 15, 10, 30)
        ranges = _compute_stats_ranges(now_utc, "Europe/Berlin")
        # Local midnight of 2024-03-15 CET = 2024-03-14 23:00 UTC
        assert ranges[0]["from"] == int(
            datetime(2024, 3, 14, 23, 0, tzinfo=UTC).timestamp() * 1000
        )

    def test_week_start_is_iso_monday(self) -> None:
        """The second range starts at local midnight of the preceding ISO Monday."""
        # 2024-03-15 (Friday) → ISO Monday = 2024-03-11
        now_utc = self._now(2024, 3, 15, 10, 30)
        ranges = _compute_stats_ranges(now_utc, "UTC")
        week_from = ranges[1]["from"]
        # 2024-03-11 00:00 UTC = 1710115200000 ms
        assert week_from == int(
            datetime(2024, 3, 11, 0, 0, tzinfo=UTC).timestamp() * 1000
        )

    def test_month_start_is_first_day_of_month(self) -> None:
        """The third range starts at local midnight on the 1st of the current month."""
        now_utc = self._now(2024, 3, 15, 10, 30)
        ranges = _compute_stats_ranges(now_utc, "UTC")
        month_from = ranges[2]["from"]
        assert month_from == int(
            datetime(2024, 3, 1, 0, 0, tzinfo=UTC).timestamp() * 1000
        )

    def test_year_start_is_january_first(self) -> None:
        """The fourth range starts at local midnight on January 1st of the current year."""
        now_utc = self._now(2024, 3, 15, 10, 30)
        ranges = _compute_stats_ranges(now_utc, "UTC")
        year_from = ranges[3]["from"]
        assert year_from == int(
            datetime(2024, 1, 1, 0, 0, tzinfo=UTC).timestamp() * 1000
        )

    def test_utc_offset_is_correct_for_positive_offset(self) -> None:
        """UTC offset for a UTC+1 timezone is 1."""
        # 2024-01-15 (no DST in winter) UTC+1 for Europe/Berlin
        now_utc = self._now(2024, 1, 15, 12, 0)
        ranges = _compute_stats_ranges(now_utc, "Europe/Berlin")
        assert ranges[0]["utc_offset"] == 1

    def test_utc_offset_is_zero_for_utc(self) -> None:
        """UTC offset for the UTC timezone is 0."""
        now_utc = self._now(2024, 3, 15, 10, 30)
        ranges = _compute_stats_ranges(now_utc, "UTC")
        for r in ranges:
            assert r["utc_offset"] == 0

    def test_all_ranges_have_correct_lod_values(self) -> None:
        """Each range has the correct lod value from BlancoTimeRange."""
        now_utc = self._now(2024, 3, 15, 10, 30)
        ranges = _compute_stats_ranges(now_utc, "UTC")
        assert ranges[0]["lod"] == int(BlancoTimeRange.DAY)
        assert ranges[1]["lod"] == int(BlancoTimeRange.WEEK)
        assert ranges[2]["lod"] == int(BlancoTimeRange.MONTH)
        assert ranges[3]["lod"] == int(BlancoTimeRange.YEAR)

    def test_returns_exactly_four_ranges(self) -> None:
        """_compute_stats_ranges always returns exactly 4 range dicts."""
        now_utc = self._now(2024, 3, 15, 10, 30)
        ranges = _compute_stats_ranges(now_utc, "UTC")
        assert len(ranges) == 4

    def test_all_ranges_have_iso_week_true(self) -> None:
        """Every range descriptor includes iso_week=True."""
        now_utc = self._now(2024, 3, 15, 10, 30)
        ranges = _compute_stats_ranges(now_utc, "UTC")
        for r in ranges:
            assert r["iso_week"] is True


# ── _extract_stat_water_l ──────────────────────────────────────────────────────


class TestExtractStatWaterL:
    """Tests for the _extract_stat_water_l helper."""

    def _item(self, par: str, val: float | list) -> StatTotalItem:
        """Build a minimal StatTotalItem."""
        return {"par": par, "cnt": 1, "func": 0, "val": val}

    def test_returns_value_divided_by_1000_for_matching_param(self) -> None:
        """Matching param with numeric val returns val / 1000 in litres."""
        total: list[StatTotalItem] = [self._item("disp_wtr_amt", 5000)]
        result = _extract_stat_water_l(total, "disp_wtr_amt")
        assert result == pytest.approx(5.0)

    def test_returns_none_when_param_not_found(self) -> None:
        """Returns None when the param name is not present in the total list."""
        total: list[StatTotalItem] = [self._item("other_param", 1000)]
        result = _extract_stat_water_l(total, "disp_wtr_amt")
        assert result is None

    def test_returns_none_for_empty_total_list(self) -> None:
        """Returns None when the total list is empty."""
        result = _extract_stat_water_l([], "disp_wtr_amt")
        assert result is None

    def test_returns_none_when_val_is_a_list(self) -> None:
        """Returns None when val is a list (distribution result, not a scalar)."""
        total: list[StatTotalItem] = [self._item("disp_wtr_amt", [100, 200, 300])]
        result = _extract_stat_water_l(total, "disp_wtr_amt")
        assert result is None

    def test_returns_first_matching_item(self) -> None:
        """When multiple entries share the same par, the first one is used."""
        total: list[StatTotalItem] = [
            self._item("disp_wtr_amt", 3000),
            self._item("disp_wtr_amt", 9000),
        ]
        result = _extract_stat_water_l(total, "disp_wtr_amt")
        assert result == pytest.approx(3.0)

    def test_handles_float_val(self) -> None:
        """A float val is divided by 1000 correctly."""
        total: list[StatTotalItem] = [self._item("wtr_flow", 1500.5)]
        result = _extract_stat_water_l(total, "wtr_flow")
        assert result == pytest.approx(1.5005)
