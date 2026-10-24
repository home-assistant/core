"""Recovery regressions for reconfigure, interrupted batches and reauth (synthetic)."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from yarl import URL

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.solaredge.application_credentials import (
    async_get_auth_implementation,
)
from homeassistant.components.solaredge.config_flow import SolarEdgeConfigFlow
from homeassistant.components.solaredge.coordinator import SolarEdgeV2Coordinator
from homeassistant.components.solaredge.sensor import SENSOR_TYPES, SolarEdgeV2Sensor
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_entry_oauth2_flow as oauth
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import UpdateFailed

from .test_community import register_basic
from .test_v2_runtime import BASE, coordinator, entry_data

# Arbitrary synthetic clock and credentials.
NOW = datetime(2034, 2, 3, 8, tzinfo=UTC)
CLOCK = "homeassistant.components.solaredge.coordinator.dt_util.utcnow"
WEB_OLD = {"username": "synthetic-old-web", "password": "synthetic-old-password"}
WEB_NEW = {"username": "synthetic-new-web", "password": "synthetic-new-password"}
ORDER = [
    ("lifetime", 24, "/v2/sites/123/lifetime-energy"),
    ("power", 2, "/v2/sites/123/power"),
    ("metadata", 168, "/v2/sites/123"),
    ("inventory", 168, "/v2/sites/123/devices"),
    ("day", 4, "/v2/sites/123/overview"),
    ("month", 4, "/v2/sites/123/overview"),
    ("year", 4, "/v2/sites/123/overview"),
    ("storage", 4, "/v2/sites/123/storage/lifetime-energy"),
]


def _paths(aioclient_mock: AiohttpClientMocker) -> list[str]:
    return sorted(call[1].path for call in aioclient_mock.mock_calls)


@pytest.mark.usefixtures("recorder_mock", "mock_setup_entry")
@pytest.mark.parametrize(
    ("submitted", "expected_web", "error"),
    [
        pytest.param({"use_oauth": True}, WEB_OLD, None, id="omitted-keeps"),
        pytest.param(
            {"use_oauth": True, "web_auth": {"username": "", "password": ""}},
            {},
            None,
            id="blank-clears",
        ),
        pytest.param(
            {"use_oauth": True, "web_auth": WEB_NEW}, WEB_NEW, None, id="replaced"
        ),
        pytest.param(
            {"use_oauth": True, "web_auth": WEB_NEW},
            None,
            "invalid_auth",
            id="replacement-rejected",
        ),
    ],
)
async def test_v2_reconfigure_web_section_semantics(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    submitted: dict[str, Any],
    expected_web: dict[str, str] | None,
    error: str | None,
) -> None:
    """Only a submitted web section changes saved web settings of a V2 entry."""
    original = {
        **entry_data(),
        "site_metadata": {"siteId": 123, "name": "Synthetic site"},
        **WEB_OLD,
    }
    entry = MockConfigEntry(
        domain="solaredge", unique_id="synthetic-identity", data=deepcopy(original)
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    with (
        patch("homeassistant.components.solaredge.config_flow.SolarEdgeWeb") as web,
        patch.object(
            SolarEdgeConfigFlow, "async_step_oauth_application", new_callable=AsyncMock
        ) as consent,
        patch.object(hass.config_entries, "async_reload", return_value=True) as reload,
    ):
        web.return_value.async_get_equipment = AsyncMock(
            side_effect=ClientResponseError(MagicMock(), (), status=401)
            if error
            else None
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], submitted
        )
        await hass.async_block_till_done()
    consent.assert_not_awaited()
    assert aioclient_mock.call_count == 0
    assert web.called is bool(submitted.get("web_auth", {}).get("username"))
    if error:
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error}
        assert dict(entry.data) == original
        reload.assert_not_awaited()
        return
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    reload.assert_awaited_once_with(entry.entry_id)
    without_web = {key: value for key, value in original.items() if key not in WEB_OLD}
    assert dict(entry.data) == {**without_web, **expected_web}
    assert entry.unique_id == "synthetic-identity"


@pytest.mark.parametrize(
    "completed",
    [pytest.param(0, id="before-first-job"), pytest.param(3, id="after-three-jobs")],
)
async def test_interrupted_batch_snapshot_resumes_only_unfinished(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, completed: int
) -> None:
    """A durable mid-batch save restored after abrupt process death resumes safely."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    first = coordinator(hass, entry)
    snapshots: list[dict[str, Any]] = []

    async def capture(state: dict[str, Any]) -> None:
        snapshots.append(deepcopy(state))

    register_basic(aioclient_mock, NOW)
    with (
        patch(CLOCK, return_value=NOW),
        patch.object(first.store, "async_save", side_effect=capture),
    ):
        await first._async_update_data()
    assert aioclient_mock.call_count == 8
    # Save 0 is the pre-I/O reservation; save n follows the n-th completed job.
    snapshot = snapshots[completed]
    assert snapshot["failed"] is True
    assert len(snapshot["calls"]) == 8
    # The process dies here: only this persisted state survives.
    await Store(hass, 1, f"solaredge.v2.{entry.entry_id}").async_save(snapshot)
    fresh = coordinator(hass, entry)

    early = NOW + timedelta(minutes=30)
    aioclient_mock.clear_requests()
    register_basic(aioclient_mock, early)
    with patch(CLOCK, return_value=early):
        await fresh._async_setup()
        with pytest.raises(UpdateFailed, match="paused"):
            await fresh._async_update_data()
    assert aioclient_mock.call_count == 0

    later = NOW + timedelta(hours=2, seconds=1)
    aioclient_mock.clear_requests()
    register_basic(aioclient_mock, later)
    with patch(CLOCK, return_value=later):
        await fresh._async_update_data()
    done = {key for key, _, _ in ORDER[:completed]}
    expected = [
        path
        for key, hours, path in ORDER
        if key not in done or NOW + timedelta(hours=hours) <= later
    ]
    assert _paths(aioclient_mock) == sorted(expected)
    for key, hours, _ in ORDER:
        start = NOW if key in done and NOW + timedelta(hours=hours) > later else later
        assert fresh.state["due"][key] == (start + timedelta(hours=hours)).timestamp()
    # Earlier reservations are kept; only the resumed requests add new ones.
    assert len(fresh.state["calls"]) == 8 + len(expected)
    assert fresh.state["failed"] is False


@pytest.mark.usefixtures("recorder_mock")
async def test_successful_reauth_clears_only_metadata_denial(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """Reused reauthorization site metadata is current; other denials remain."""
    hass.config.external_url = "https://ha.example.com"
    impl = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic", "synthetic")
    )
    oauth.async_register_implementation(hass, "solaredge", impl)
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    old = SolarEdgeV2Coordinator(hass, entry, oauth.OAuth2Session(hass, entry, impl))
    old.state["permissions"] = {"metadata": "denied", "inventory": "denied"}
    aioclient_mock.get(BASE + "/sites/123/lifetime-energy", status=401)
    with patch(CLOCK, return_value=NOW), pytest.raises(ConfigEntryAuthFailed):
        await old._async_update_data()
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "solaredge"}
    )
    aioclient_mock.post(
        BASE + "/oauth2/token",
        json={
            "access_token": "synthetic-new-access",
            "refresh_token": "synthetic-new-refresh",
            "token_type": "Bearer",
            "expires_in": 7200,
        },
    )
    aioclient_mock.get(
        BASE + "/sites/123",
        json={
            "siteId": 123,
            "activationStatus": "Active",
            "location": {"timezone": "Europe/Amsterdam"},
        },
    )
    client = await hass_client()
    response = await client.get(
        "/auth/external/callback/solaredge",
        params={
            "external_id": URL(result["url"]).query["external_id"],
            "code": "synthetic-code",
        },
    )
    assert response.status == 200
    with (
        patch(CLOCK, return_value=NOW),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"]["refresh_token"] == "synthetic-new-refresh"

    restored = SolarEdgeV2Coordinator(
        hass, entry, oauth.OAuth2Session(hass, entry, impl)
    )
    await restored._async_setup()
    assert restored.state["permissions"] == {"inventory": "denied"}
    site = next(item for item in SENSOR_TYPES if item.key == "site_details")
    sensor = SolarEdgeV2Sensor(restored, site)
    assert sensor.available
    assert sensor.native_value == "active"

    aioclient_mock.clear_requests()
    register_basic(aioclient_mock, NOW)
    with patch(CLOCK, return_value=NOW):
        await restored._async_update_data()
    # The reauthorization response is reused: no extra site metadata request.
    assert "/v2/sites/123" not in _paths(aioclient_mock)
    assert "/v2/sites/123/devices" in _paths(aioclient_mock)
