"""Tests for the Bosch Smart Home Camera config/options flow helpers."""

import base64
from http import HTTPStatus
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.bosch_shc_camera import config_flow as cf_module
from homeassistant.components.bosch_shc_camera.config_flow import (
    AuthServerOutageError,
    _detect_token_client_id,
    _do_refresh,
    _flatten_sections,
)
from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


def test_flatten_sections_empty() -> None:
    """An empty submit dict flattens to an empty dict."""
    assert _flatten_sections({}) == {}


def test_flatten_sections_single_section() -> None:
    """Fields nested under one section key are lifted to the top level."""
    user_input = {"features": {"enable_snapshots": False}}
    assert _flatten_sections(user_input) == {"enable_snapshots": False}


def test_flatten_sections_multiple_sections() -> None:
    """Fields from multiple sections are merged into one flat dict."""
    user_input = {
        "features": {"enable_snapshots": False},
        "auth": {"migrate_to_oss_client": True},
    }
    assert _flatten_sections(user_input) == {
        "enable_snapshots": False,
        "migrate_to_oss_client": True,
    }


def test_flatten_sections_missing_section_is_treated_as_empty() -> None:
    """A section key HA omitted (empty section) does not raise."""
    user_input = {"features": {"enable_snapshots": False}}
    # "events_storage"/"auth" section keys are absent entirely — must not raise.
    assert _flatten_sections(user_input) == {"enable_snapshots": False}


def test_flatten_sections_passes_through_non_section_keys() -> None:
    """Top-level keys that aren't section keys pass through unchanged."""
    user_input = {
        "features": {"enable_snapshots": False},
        "some_legacy_flat_key": "value",
    }
    assert _flatten_sections(user_input) == {
        "enable_snapshots": False,
        "some_legacy_flat_key": "value",
    }


def test_flatten_sections_duplicate_key_across_sections_raises() -> None:
    """Two sections both defining the same field name raises ValueError."""
    user_input = {
        "features": {"enable_snapshots": False},
        "auth": {"enable_snapshots": True},
    }
    with pytest.raises(ValueError, match="duplicate key"):
        _flatten_sections(user_input)


def test_flatten_sections_duplicate_top_level_and_section_raises() -> None:
    """A top-level key colliding with a section-provided field raises ValueError."""
    user_input = {
        "features": {"enable_snapshots": False},
        "enable_snapshots": True,
    }
    with pytest.raises(ValueError, match="duplicate key"):
        _flatten_sections(user_input)


def test_flatten_sections_does_not_mutate_input() -> None:
    """The input dict is never mutated."""
    user_input = {"features": {"enable_snapshots": False}}
    original = {"features": {"enable_snapshots": False}}
    _flatten_sections(user_input)
    assert user_input == original


@pytest.mark.parametrize(
    ("bearer_token", "expected"),
    [
        pytest.param("", None, id="empty-token"),
        pytest.param("not-a-jwt", None, id="not-enough-parts"),
        pytest.param(
            "only.onepart", None, id="two-parts-no-padding-issue-but-bad-json"
        ),
    ],
)
def test_detect_token_client_id_invalid_tokens(
    bearer_token: str, expected: str | None
) -> None:
    """Malformed tokens return None instead of raising."""
    assert _detect_token_client_id(bearer_token) == expected


def test_detect_token_client_id_valid_jwt() -> None:
    """A well-formed JWT's `azp` claim is extracted."""
    payload = base64.urlsafe_b64encode(
        json.dumps({"azp": "oss_residential_app"}).encode()
    ).rstrip(b"=")
    token = f"header.{payload.decode()}.signature"
    assert _detect_token_client_id(token) == "oss_residential_app"


def test_detect_token_client_id_missing_azp_claim() -> None:
    """A valid JWT without an `azp` claim returns None."""
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "x"}).encode()).rstrip(b"=")
    token = f"header.{payload.decode()}.signature"
    assert _detect_token_client_id(token) is None


@pytest.mark.usefixtures("current_request_with_host", "mock_bosch_cloud_session")
async def test_full_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_setup_entry: AsyncMock,
) -> None:
    """A fresh user-initiated flow completes OAuth and creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://my.home-assistant.io/redirect/oauth",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bosch Smart Home Camera"
    assert result["data"]["bearer_token"] == "mock-access-token"
    assert result["data"]["refresh_token"] == "mock-refresh-token"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host", "mock_bosch_cloud_session")
async def test_duplicate_entry_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_setup_entry: AsyncMock,
) -> None:
    """A second setup attempt aborts once an entry already exists (single_config_entry)."""
    existing = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN)
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    # manifest.json's single_config_entry:true makes HA-core's own flow
    # manager reject the second flow before our unique_id check ever runs.
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("current_request_with_host", "mock_bosch_cloud_session")
async def test_reauth_flow_updates_existing_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_setup_entry: AsyncMock,
) -> None:
    """Reauth replaces the stored tokens on the existing entry instead of creating a new one."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={"bearer_token": "stale-token", "refresh_token": "stale-refresh"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://my.home-assistant.io/redirect/oauth",
        },
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["bearer_token"] == "mock-access-token"
    assert entry.data["refresh_token"] == "mock-refresh-token"
    # Reauth updates in place — never a second entry.
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_options_flow_toggle_enable_snapshots(hass: HomeAssistant) -> None:
    """Submitting the options form persists a real feature toggle through hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={"bearer_token": "tok", "refresh_token": "reftok"},
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"features": {"enable_snapshots": False}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["enable_snapshots"] is False


@pytest.mark.usefixtures("current_request_with_host", "mock_bosch_cloud_session")
async def test_camera_access_denied_aborts_before_creating_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_setup_entry: AsyncMock,
) -> None:
    """A successful OAuth exchange whose account can't reach the camera API must abort.

    A successful token exchange only proves SingleKey ID login succeeded —
    Bosch's camera API can still reject the fresh token for an account whose
    camera registration never completed (bug-hunt 2026-07-27, Copilot review
    round 4).
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://my.home-assistant.io/redirect/oauth",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    with patch.object(
        cf_module.BoschCameraConfigFlow,
        "_async_verify_camera_access",
        AsyncMock(return_value=False),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "camera_access_denied"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.usefixtures("current_request_with_host", "mock_bosch_cloud_session")
async def test_camera_access_transient_aborts_with_cannot_connect(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_setup_entry: AsyncMock,
) -> None:
    """An inconclusive camera-access check (429/5xx) must abort with retry semantics.

    It must not silently create an unverified entry (bug-hunt 2026-07-27,
    Copilot review round 6).
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://my.home-assistant.io/redirect/oauth",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    with patch.object(
        cf_module.BoschCameraConfigFlow,
        "_async_verify_camera_access",
        AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_verify_camera_access_returns_none_on_429() -> None:
    """A 429 (rate limited) must not be treated as account denial, nor silently verified.

    It says nothing about whether this account can reach the camera API,
    only that this one request didn't land — accepting it as verified would
    create an unverified entry that could immediately fail its first
    coordinator refresh; the caller aborts with retry semantics instead
    (bug-hunt 2026-07-27, Copilot review round 6, refining round 5's fix).
    """
    session = MagicMock()
    resp = MagicMock()
    resp.status = 429
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    session.get = MagicMock(return_value=resp)

    flow = cf_module.BoschCameraConfigFlow.__new__(cf_module.BoschCameraConfigFlow)
    flow.hass = MagicMock()

    with patch(
        "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
        AsyncMock(return_value=session),
    ):
        assert await flow._async_verify_camera_access("tok") is None


async def test_verify_camera_access_returns_none_on_5xx() -> None:
    """A 5xx (Bosch-side outage) must not be treated as account denial either."""
    session = MagicMock()
    resp = MagicMock()
    resp.status = 503
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    session.get = MagicMock(return_value=resp)

    flow = cf_module.BoschCameraConfigFlow.__new__(cf_module.BoschCameraConfigFlow)
    flow.hass = MagicMock()

    with patch(
        "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
        AsyncMock(return_value=session),
    ):
        assert await flow._async_verify_camera_access("tok") is None


async def test_verify_camera_access_returns_false_on_403() -> None:
    """A definitive rejection (e.g. 403) must still deny — only 429/5xx are transient."""
    session = MagicMock()
    resp = MagicMock()
    resp.status = 403
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    session.get = MagicMock(return_value=resp)

    flow = cf_module.BoschCameraConfigFlow.__new__(cf_module.BoschCameraConfigFlow)
    flow.hass = MagicMock()

    with patch(
        "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
        AsyncMock(return_value=session),
    ):
        assert await flow._async_verify_camera_access("tok") is False


async def test_verify_camera_access_returns_none_on_timeout() -> None:
    """A network-layer timeout is inconclusive, same as a 429/5xx response.

    A prior version returned True unconditionally here, but that was
    inconsistent with the 429/5xx handling and weakened the Bronze
    test-before-configure guarantee this check exists to provide
    (Copilot review round 7).
    """
    flow = cf_module.BoschCameraConfigFlow.__new__(cf_module.BoschCameraConfigFlow)
    flow.hass = MagicMock()

    with patch(
        "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
        AsyncMock(side_effect=TimeoutError()),
    ):
        assert await flow._async_verify_camera_access("tok") is None


async def test_verify_camera_access_returns_none_on_client_error() -> None:
    """A network-layer connection error is inconclusive, same as a timeout."""
    flow = cf_module.BoschCameraConfigFlow.__new__(cf_module.BoschCameraConfigFlow)
    flow.hass = MagicMock()

    with patch(
        "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
        AsyncMock(side_effect=aiohttp.ClientError("connection reset")),
    ):
        assert await flow._async_verify_camera_access("tok") is None


async def test_do_refresh_raises_auth_server_outage_on_429() -> None:
    """A 429 (rate limited) must route through the same transient/backoff path as a 5xx.

    It says nothing about the refresh token's validity, so it must never
    count toward the invalid-grant/reauth escalation (bug-hunt 2026-07-27,
    Copilot review round 6).
    """
    resp = MagicMock()
    resp.status = 429
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.post = MagicMock(return_value=resp)

    with pytest.raises(AuthServerOutageError):
        await _do_refresh(session, "old_refresh_token")
