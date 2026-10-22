"""Synthetic native regressions for shared limits and protocol-preserving edits."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from aiosolaredge.v2 import RateLimitError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.solaredge.config_flow import SolarEdgeConfigFlow
from homeassistant.components.solaredge.v2_budget import MAX_CALLS, WINDOW, get_budget
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from .test_community import register_basic
from .test_v2_runtime import BASE, coordinator, entry_data

# Arbitrary synthetic clock and quota.
NOW = datetime(2032, 4, 5, tzinfo=UTC)
QUOTA = {"x-ratelimit-remaining-month": 17}
CLOCK = "homeassistant.components.solaredge.v2_budget.dt_util.utcnow"
V1_DETAILS = "https://monitoringapi.solaredge.com/site/123/details"


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize("caller", ["coordinator", "config_flow"])
@pytest.mark.parametrize("limit", ["provider", "minute", "month"])
async def test_local_refusal_preserves_shared_budget(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caller: str,
    limit: str,
) -> None:
    """Real client reservations refuse I/O without amplifying another entry's pause."""
    budget = get_budget(hass)
    with patch(CLOCK, return_value=NOW):
        if limit == "provider":
            await budget.pause(RateLimitError("120", quota=QUOTA, http_status=429))
            later = NOW + timedelta(minutes=30)
            wait_until = NOW + timedelta(hours=1)
        else:
            stamp = NOW if limit == "minute" else NOW - timedelta(days=1)
            calls = [stamp.timestamp()] * (10 if limit == "minute" else MAX_CALLS)
            budget.state = {"calls": calls, "blocked": 0, "quota": QUOTA.copy()}
            await budget.store.async_save(budget.state)
            later = NOW + timedelta(seconds=1)
            wait_until = stamp + (timedelta(minutes=1) if limit == "minute" else WINDOW)
    before = deepcopy(budget.state)
    with patch(CLOCK, return_value=later):
        if caller == "coordinator":
            coord = coordinator(hass, _entry(hass))
            # Earlier genuine provider evidence for this entry must survive.
            coord.state.update(quota={"synthetic": 1}, quota_kind="monthly")
            # No API method mock: the actual client must hit the shared guard.
            with pytest.raises(UpdateFailed, match="quota exceeded"):
                await coord._async_update_data()
            # Entry reservations are not refunded; it waits only the local remainder.
            assert len(coord.state["calls"]) == 8
            assert coord.state["failed"] is True
            assert coord.state["next_poll"] == wait_until.timestamp()
            assert set(coord.state["due"].values()) == {wait_until.timestamp()}
            assert coord.state["quota"] == {"synthetic": 1}
            assert coord.state["quota_kind"] == "monthly"
            # Its own failed pause still blocks a second attempt without I/O.
            with pytest.raises(UpdateFailed, match="polling paused"):
                await coord._async_update_data()
            assert len(coord.state["calls"]) == 8
        else:
            flow = SolarEdgeConfigFlow()
            flow.hass = hass
            flow.context = {"source": SOURCE_USER}
            flow._oauth_site_id = "123"
            result = await flow.async_oauth_create_entry(entry_data())
            assert result["type"] is FlowResultType.ABORT
            assert result["reason"] == "cannot_connect"
    assert aioclient_mock.call_count == 0
    assert budget.state == before
    # A fresh budget instance reads exactly the same persisted quota/reservations.
    restored = type(budget)(hass)
    assert await restored._load() == before
    if limit == "provider":
        assert budget.state["blocked"] == (NOW + timedelta(hours=1)).timestamp()
        assert budget.state["quota"] == QUOTA
    else:
        assert budget.state["blocked"] == 0


async def test_staggered_entries_do_not_extend_provider_pause(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Two native entries cannot keep each other paused with zero provider I/O."""
    budget = get_budget(hass)
    first = coordinator(hass, _entry(hass))
    second = coordinator(hass, _entry(hass))
    aioclient_mock.get(
        BASE + "/sites/123/lifetime-energy",
        status=429,
        headers={"Retry-After": "120", "x-ratelimit-remaining-minute": "0"},
    )
    with patch(CLOCK, return_value=NOW), pytest.raises(UpdateFailed):
        await first._async_update_data()
    assert aioclient_mock.call_count == 1
    deadline = (NOW + timedelta(hours=1)).timestamp()
    assert budget.state["blocked"] == deadline
    assert first.state["next_poll"] == deadline
    evidence = deepcopy(budget.state)

    with (
        patch(CLOCK, return_value=NOW + timedelta(minutes=30)),
        pytest.raises(UpdateFailed, match="quota exceeded"),
    ):
        await second._async_update_data()
    assert aioclient_mock.call_count == 1
    assert budget.state == evidence
    assert second.state["next_poll"] == deadline

    # The original deadline, not a refusal-extended one, governs the next real read.
    resumed = NOW + timedelta(hours=1, seconds=1)
    aioclient_mock.clear_requests()
    register_basic(aioclient_mock, resumed)
    with patch(CLOCK, return_value=resumed):
        data = await first._async_update_data()
    assert data["lifetime_energy"].value == 12000
    assert aioclient_mock.call_count == 8
    assert budget.state["blocked"] == deadline


async def test_mid_batch_local_cpm_refusal_is_not_provider_pause(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The local rolling-minute guard stops I/O but never starts an hour-long pause."""
    budget = get_budget(hass)
    budget.state = {"calls": [(NOW - timedelta(seconds=30)).timestamp()] * 4}
    budget.state["blocked"] = 0
    await budget.store.async_save(budget.state)
    register_basic(aioclient_mock, NOW)
    coord = coordinator(hass, _entry(hass))
    with (
        patch(CLOCK, return_value=NOW),
        pytest.raises(UpdateFailed, match="quota exceeded"),
    ):
        await coord._async_update_data()
    # Six real reads fit beside four earlier reservations; the seventh is refused.
    assert aioclient_mock.call_count == 6
    assert len(budget.state["calls"]) == 10
    assert budget.state["blocked"] == 0
    assert "quota" not in budget.state
    assert coord.state["next_poll"] == (NOW + timedelta(seconds=30)).timestamp()
    assert coord.state["readings"]["lifetime_energy"]["value"] == 12000


@pytest.mark.parametrize("caller", ["coordinator", "config_flow"])
async def test_transport_429_still_pauses_every_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caller: str
) -> None:
    """Actual HTTP 429 remains authoritative account-wide quota evidence."""
    headers = {"Retry-After": "7200", "x-ratelimit-remaining-month": "0"}
    path = "/sites/123/lifetime-energy" if caller == "coordinator" else "/sites/123"
    aioclient_mock.get(BASE + path, status=429, headers=headers)
    budget = get_budget(hass)
    deadline = (NOW + timedelta(hours=2)).timestamp()
    with patch(CLOCK, return_value=NOW):
        if caller == "coordinator":
            coord = coordinator(hass, _entry(hass))
            with pytest.raises(UpdateFailed, match="quota exceeded"):
                await coord._async_update_data()
            assert coord.state["quota"] == {"x-ratelimit-remaining-month": 0}
            assert coord.state["quota_kind"] == "monthly"
            assert coord.state["next_poll"] == deadline
        else:
            flow = SolarEdgeConfigFlow()
            flow.hass = hass
            flow.context = {"source": SOURCE_USER}
            flow._oauth_site_id = "123"
            result = await flow.async_oauth_create_entry(entry_data())
            assert result["reason"] == "cannot_connect"
    assert aioclient_mock.call_count == 1
    assert budget.state["blocked"] == deadline
    assert budget.state["quota"] == {"x-ratelimit-remaining-month": 0}
    restored = type(budget)(hass)
    assert (await restored._load())["blocked"] == deadline


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(("api_version", "expected"), [(2, True), (None, False)])
async def test_reconfigure_defaults_to_current_protocol(
    hass: HomeAssistant, api_version: int | None, expected: bool
) -> None:
    """The native initial schema must not suggest an implicit protocol change."""
    data = entry_data() if api_version else {"site_id": "123", "api_key": "synthetic"}
    entry = MockConfigEntry(domain="solaredge", data=data)
    entry.add_to_hass(hass)
    initial = await entry.start_reconfigure_flow(hass)
    marker = next(
        key for key in initial["data_schema"].schema if key.schema == "use_oauth"
    )
    assert marker.default() is expected
    assert marker.description["suggested_value"] is expected


@pytest.mark.usefixtures("recorder_mock", "mock_setup_entry")
@pytest.mark.parametrize("selection", ["omitted", "kept", "unchanged", "cleared"])
async def test_v2_web_reconfigure_keeps_oauth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    selection: str,
) -> None:
    """Native update/reload preserves entry, registry and OAuth without fresh consent."""
    original = {
        **entry_data(),
        "site_metadata": {"siteId": 123, "name": "Synthetic site"},
        "username": "synthetic-web",
        "password": "synthetic-old-password",
    }
    entry = MockConfigEntry(
        domain="solaredge", unique_id="synthetic-identity", data=deepcopy(original)
    )
    entry.add_to_hass(hass)
    registry = entity_registry
    entity = registry.async_get_or_create(
        "sensor", "solaredge", "123_lifetime_energy", config_entry=entry
    )
    initial = await entry.start_reconfigure_flow(hass)
    assert initial["step_id"] == "reconfigure"
    web = {"username": "synthetic-web", "password": "synthetic-new-password"}
    expected = {**original, "password": "synthetic-new-password"}
    submitted: dict = {"web_auth": web}
    if selection == "kept":
        submitted["use_oauth"] = True
    elif selection == "unchanged":
        # Exactly the prefilled form, as the frontend submits it.
        web = {"username": "synthetic-web", "password": "synthetic-old-password"}
        submitted = {"use_oauth": True, "api_auth": {"api_key": ""}, "web_auth": web}
        expected = original
    elif selection == "cleared":
        submitted = {"use_oauth": True, "web_auth": {"username": "", "password": ""}}
        expected = {
            key: value
            for key, value in original.items()
            if key not in ("username", "password")
        }
    with (
        patch.object(
            SolarEdgeConfigFlow, "_async_check_web_login", return_value=True
        ) as validate,
        patch.object(
            SolarEdgeConfigFlow, "async_step_oauth_application", new_callable=AsyncMock
        ) as consent,
        patch.object(hass.config_entries, "async_reload", return_value=True) as reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            initial["flow_id"], submitted
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    if selection == "cleared":
        validate.assert_not_awaited()
    else:
        validate.assert_awaited_once_with("123", web["username"], web["password"])
    consent.assert_not_awaited()
    reload.assert_awaited_once_with(entry.entry_id)
    assert aioclient_mock.call_count == 0
    # Read actual stored entry, not a captured helper payload.
    saved = hass.config_entries.async_get_entry(entry.entry_id)
    assert saved is entry
    assert dict(saved.data) == expected
    assert saved.unique_id == "synthetic-identity"
    assert registry.async_get(entity.entity_id).unique_id == "123_lifetime_energy"
    assert registry.async_get(entity.entity_id).config_entry_id == entry.entry_id


@pytest.mark.usefixtures("recorder_mock", "mock_setup_entry")
@pytest.mark.parametrize(
    ("case", "use_oauth", "details", "error"),
    [
        ("missing_key", False, None, ("base", "v1_api_key_required")),
        ("invalid_key", False, {}, ("site_id", "invalid_api_key")),
        ("key_while_v2", True, None, ("base", "api_key_with_oauth")),
        ("explicit_v1", False, {"details": {"status": "Active"}}, None),
    ],
)
async def test_v2_protocol_switch_requires_explicit_valid_v1(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    case: str,
    use_oauth: bool,
    details: dict | None,
    error: tuple[str, str] | None,
) -> None:
    """Only an explicit V1 choice with a validated V1 key can replace V2."""
    original = entry_data()
    entry = MockConfigEntry(domain="solaredge", data=deepcopy(original))
    entry.add_to_hass(hass)
    initial = await entry.start_reconfigure_flow(hass)
    submitted: dict = {"use_oauth": use_oauth}
    if case == "missing_key":
        submitted["web_auth"] = {"username": "synthetic-web", "password": "synthetic"}
    else:
        submitted["api_auth"] = {"api_key": "synthetic-v1-key"}
    if details is not None:
        aioclient_mock.get(V1_DETAILS, json=details)
    with (
        patch.object(SolarEdgeConfigFlow, "_async_check_web_login") as web,
        patch.object(hass.config_entries, "async_reload", return_value=True) as reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            initial["flow_id"], submitted
        )
        await hass.async_block_till_done()
    web.assert_not_awaited()
    assert aioclient_mock.call_count == (0 if details is None else 1)
    if error:
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {error[0]: error[1]}
        assert dict(entry.data) == original
        reload.assert_not_awaited()
    else:
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert dict(entry.data) == {"site_id": "123", "api_key": "synthetic-v1-key"}
        reload.assert_awaited_once_with(entry.entry_id)
