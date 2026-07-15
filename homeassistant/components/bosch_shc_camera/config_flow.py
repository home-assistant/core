"""Config flow for Bosch Smart Home Camera integration.

Setup flow — menu step "user" offers a choice of login method:
  "auto_login"   — one-click browser login via Bosch SingleKey ID, using the
                   my.home-assistant.io redirect for automatic callback.
  "manual_login" — copy/paste fallback (steps "manual_login"/"manual_paste")
                   for cases where the automatic redirect strands the user in
                   the wrong browser tab/webview (seen on the HA Companion
                   App and desktop Safari with SingleKey ID's multi-hop
                   redirect chain).

Options flow:
  Step "init"          — feature toggles
  Step "relogin_show"  — shows login URL as read-only field
  Step "relogin_paste" — paste redirect URL

OAuth2 details:
  Issuer:       smarthome.authz.bosch.com/auth/realms/home_auth_provider
  Client ID:    oss_residential_app
  Redirect URI: https://my.home-assistant.io/redirect/oauth
  Scopes:       email offline_access profile openid

application_credentials:
  The (CLIENT_ID, CLIENT_SECRET) pair below is Bosch's public OSS client
  credential — identical in every Android APK, not a per-user secret. It is
  still routed through HA-core's `application_credentials` platform (see
  `application_credentials.py`): the default `ClientCredential` is
  auto-imported via `async_import_client_credential()`, the same pattern
  `overkiz`/`vicare`/`ondilo_ico` use for a built-in public OAuth client.

  The import is called from BOTH `__init__.py`'s `async_setup()` (so it is
  present for already-configured installs, reloads, and anything else that
  touches application_credentials outside a flow) AND
  `BoschCameraConfigFlow.async_step_user` below (so it is present for a
  BRAND NEW install too). The second call site is not redundant belt-and-
  braces — it is load-bearing: HA-core's `_load_integration`
  (`config_entries.py`) only sets up a fresh config flow's *dependency*
  domains (here: `application_credentials` itself, via manifest.json) and
  imports the `config_flow` platform module; it does NOT call this
  integration's own `async_setup()` before the flow starts (that only
  happens once a config ENTRY exists, i.e. after OAuth already succeeded
  once). Relying solely on `__init__.py`'s `async_setup()` would mean a
  first-time install's `auto_login` step reaches `AbstractOAuth2FlowHandler.
  async_step_pick_implementation` with STILL zero client credentials
  registered, which aborts the flow with `missing_credentials`/
  `missing_configuration` instead of proceeding to OAuth (caught by the
  THREE_PER_ISSUE_PER_CHANGE bug-hunt during this port — see git history).
  `async_import_client_credential` is idempotent (no-ops if the credential ID
  already exists), so calling it from both places is safe.

  This means `BoschCameraConfigFlow.async_step_user` no longer calls
  `async_register_implementation()` (removed) — HA-core's
  application_credentials component supplies the single
  `BoschOAuth2Implementation` implementation via its own provider mechanism
  (`_async_provide_implementation` -> `application_credentials.py::
  async_get_auth_implementation`), constructed from the imported
  `ClientCredential`. The manual copy/paste login fallback (`manual_login`/
  `manual_paste`/options `relogin_show`/`relogin_paste`) and the hand-rolled
  token-refresh logic in `token_auth.py` are UNCHANGED — they never went
  through `OAuth2Session`/`AbstractOAuth2Implementation.async_refresh_token`
  and still call Keycloak directly via `_do_refresh`/`_exchange_code`, using
  the same module-level CLIENT_ID/CLIENT_SECRET constants. Existing config
  entries are unaffected: this integration has never persisted
  `auth_implementation` in entry data (only `bearer_token`/`refresh_token`),
  so there is nothing to migrate.
"""

import asyncio
import base64
import hashlib
import ipaddress
import json
import logging
import secrets
from typing import Any, override
from urllib.parse import parse_qs, urlencode

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    AbstractOAuth2Implementation,
    _encode_jwt,
)
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .cloud_ssl import async_get_bosch_cloud_session

# ── Section layout (single source of truth) ───────────────────────────────────
# Sectioned options-flow groups the ~50 fields into collapsible blocks so the
# UI is browseable. The mapping below is consumed both by the section-aware
# schema builder in BoschCameraOptionsFlow.async_step_init AND by
# `_flatten_sections` (round-trip on submit). Adding a field here automatically
# wires it into the right section + flattens correctly on save.
#
# DO NOT add a key to two sections — `_flatten_sections` enforces no-collision.
OPTIONS_SECTIONS: dict[str, list[str]] = {
    "polling": [
        "scan_interval",
        "interval_status",
        "interval_events",
        "snapshot_interval",
    ],
    "features": [
        "enable_snapshots",
        "enable_sensors",
        "enable_binary_sensors",
        "motion_active_window",
        "enable_snapshot_button",
        "enable_intercom",
        "auto_play_default",
    ],
    "stream": [
        "stream_connection_type",
        "live_buffer_mode",
        "enable_go2rtc",
        "enable_green_it",
        "use_mjpeg_snapshot",
        "defer_diag_during_stream",
    ],
    "fcm": [
        "enable_fcm_push",
        "fcm_push_mode",
        "mark_events_read",
        "alert_save_snapshots",
        "alert_delete_after_send",
        "alert_notify_service",
        "alert_notify_information",
        "alert_notify_screenshot",
        "alert_notify_video",
        "alert_notify_system",
    ],
    "events_storage": [
        "folder_pattern",
        "file_pattern",
        "enable_local_save",
        "download_path",
        "enable_smb_upload",
        "upload_protocol",
        "smb_server",
        "smb_share",
        "smb_username",
        "smb_password",
        "smb_base_path",
        "smb_retention_days",
    ],
    "nvr": [
        "enable_nvr",
        "nvr_storage_target",
        "nvr_base_path",
        "nvr_smb_subpath",
        "nvr_retention_days",
        "nvr_quality",
        "nvr_preroll_seconds",
        "nvr_postroll_seconds",
        "nvr_preroll_cache_dir",
        "nvr_finalize_ring_on_event",
    ],
    # NOTE: literal strings here (not the CONF_* constants) — this dict
    # is built before the .const import at module load time.
    "webhook": [
        "enable_webhook_delivery",
        "webhook_url",
    ],
    "ptz": [
        "enable_ptz_controls",
    ],
    "frigate": [
        "frigate_endpoints_enabled",
        "frigate_bind_host",
        "frigate_bind_port",
        "frigate_ip_allowlist",
        "frigate_auth_mode",
        "frigate_token",
        "frigate_basic_user",
        "frigate_idle_timeout",
        "frigate_max_connections",
    ],
    "ai": [
        "enable_ai_description",
        "ai_task_entity",
        "ai_describe_language",
        "ai_describe_prompt",
        "ai_describe_on_motion",
        "ai_notify_include_description",
        "ai_cooldown_seconds",
        "ai_max_per_day",
        "ai_active_time_start",
        "ai_active_time_end",
        "ai_active_condition_entity",
        "ai_active_condition_state",
    ],
    "auth": [
        "force_relogin",
        "migrate_to_oss_client",
    ],
}


def _flatten_sections(user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten a section-grouped submit dict back into a single flat dict.

    Home Assistant's ``data_entry_flow.section`` helper returns sectioned input
    in the shape ``{section_key: {field: value, ...}, ...}``. The rest of the
    integration expects the legacy flat shape (one dict, all keys). This helper
    walks ``OPTIONS_SECTIONS`` and lifts every nested field up to the top
    level.

    Behaviour:
        * Non-sectioned keys (typed in directly at the top level — e.g. older
          unit tests) pass through unchanged.
        * If a section key is missing from ``user_input`` (HA may omit empty
          sections), it is treated as an empty dict rather than raising.
        * Duplicate keys across sections are caught and raise ``ValueError`` —
          a defensive guard so future ``OPTIONS_SECTIONS`` edits cannot
          silently overwrite an existing field.
        * ``user_input`` itself is never mutated.

    Pure helper, fully tested in ``tests/test_config_flow.py``.
    """
    flat: dict[str, Any] = {}
    seen_section_keys: set[str] = set()

    for section_key, _fields in OPTIONS_SECTIONS.items():
        seen_section_keys.add(section_key)
        sec_payload = user_input.get(section_key)
        if sec_payload is None:
            continue
        if not isinstance(sec_payload, dict):
            # Defensive — never expected from HA but keeps tests honest.
            continue
        for field, value in sec_payload.items():
            if field in flat:
                raise ValueError(
                    f"_flatten_sections: duplicate key {field!r} from "
                    f"section {section_key!r} — already set by another "
                    "section. Fix OPTIONS_SECTIONS."
                )
            flat[field] = value

    # Anything top-level that is NOT a section key passes through (legacy /
    # tests / programmatic options updates).
    for key, value in user_input.items():
        if key in seen_section_keys:
            continue
        if key in flat:
            raise ValueError(
                f"_flatten_sections: duplicate key {key!r} at top level "
                "and inside a section — fix caller."
            )
        flat[key] = value

    return flat


from . import (
    DEFAULT_OPTIONS,
    DOMAIN,
    BoschCameraConfigEntry,
)
from .const import (
    CONF_AI_ACTIVE_CONDITION_ENTITY,
    CONF_AI_ACTIVE_CONDITION_STATE,
    CONF_AI_ACTIVE_TIME_END,
    CONF_AI_ACTIVE_TIME_START,
    CONF_AI_COOLDOWN_SECONDS,
    CONF_AI_DESCRIBE_LANGUAGE,
    CONF_AI_DESCRIBE_ON_MOTION,
    CONF_AI_DESCRIBE_PROMPT,
    CONF_AI_MAX_PER_DAY,
    CONF_AI_NOTIFY_INCLUDE_DESCRIPTION,
    CONF_AI_TASK_ENTITY,
    CONF_DEFER_DIAG_DURING_STREAM,
    CONF_ENABLE_AI_DESCRIPTION,
    CONF_ENABLE_PTZ_CONTROLS,
    CONF_ENABLE_WEBHOOK_DELIVERY,
    CONF_WEBHOOK_URL,
    DEFAULT_AI_DESCRIBE_LANGUAGE,
    DEFAULT_AI_DESCRIBE_PROMPT,
    DEFAULT_DEFER_DIAG_DURING_STREAM,
    DEFAULT_MOTION_ACTIVE_WINDOW,
    MOTION_ACTIVE_WINDOW_MAX,
    MOTION_ACTIVE_WINDOW_MIN,
)
from .smb import smb_available, smb_dependent_features

_LOGGER = logging.getLogger(__name__)

KEYCLOAK_BASE = (
    "https://smarthome.authz.bosch.com"
    "/auth/realms/home_auth_provider/protocol/openid-connect"
)
CLIENT_ID = "oss_residential_app"
CLIENT_SECRET = (
    base64.b64decode("RjFqWnpzRzVOdHc3eDJWVmM4SjZxZ3NuaXNNT2ZhWmc=").decode()
)  # public OSS client credential — identical in every Android APK, not rotatable by us
SCOPES = "email offline_access profile openid"
REDIRECT_URI = "https://my.home-assistant.io/redirect/oauth"
REDIRECT_URI_MANUAL = "https://www.bosch.com/boschcam"
CLOUD_API = "https://residential.cbs.boschsecurity.com"


# ── PKCE helpers ──────────────────────────────────────────────────────────────


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ── OAuth2 Implementation (automatic flow via my.home-assistant.io) ──────────


class BoschOAuth2Implementation(AbstractOAuth2Implementation):
    """Bosch Keycloak OAuth2 implementation with PKCE.

    `client_id`/`client_secret` default to the module-level constants (the
    fixed public OSS client) so pre-existing direct instantiation (tests,
    and any future manual construction) keeps working unchanged. In normal
    operation `application_credentials.py::async_get_auth_implementation`
    constructs this with the values from the imported `ClientCredential`
    instead — same defaults today, but lets an admin override them via
    Settings → Application Credentials without a code change.
    """

    def __init__(
        self,
        hass: Any,
        client_id: str = CLIENT_ID,
        client_secret: str = CLIENT_SECRET,
    ) -> None:
        self.hass = hass
        self._client_id = client_id
        self._client_secret = client_secret
        self._last_verifier: str | None = None

    @property
    @override
    def name(self) -> str:
        return "Bosch SingleKey ID"

    @property
    @override
    def domain(self) -> str:
        return DOMAIN

    @property
    def redirect_uri(self) -> str:
        return REDIRECT_URI

    @override
    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate Keycloak authorization URL with PKCE challenge."""
        self._last_verifier, challenge = _pkce_pair()
        redirect_uri = self.redirect_uri
        state = _encode_jwt(
            self.hass,
            {
                "flow_id": flow_id,
                "redirect_uri": redirect_uri,
            },
        )
        params = {
            "client_id": self._client_id,
            "response_type": "code",
            "scope": SCOPES,
            "redirect_uri": redirect_uri,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        return f"{KEYCLOAK_BASE}/auth?" + urlencode(params)

    @override
    async def async_resolve_external_data(self, external_data: Any) -> dict[str, Any]:
        """Exchange authorization code for tokens."""
        code = external_data["code"]
        redirect_uri = external_data["state"]["redirect_uri"]
        session = await async_get_bosch_cloud_session(self.hass)
        async with session.post(
            f"{KEYCLOAK_BASE}/token",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": self._last_verifier,
            },
        ) as resp:
            if resp.status >= 400:
                body = await resp.text()
                _LOGGER.error(
                    "Token exchange failed: HTTP %d — %s", resp.status, body[:200]
                )
            resp.raise_for_status()
            return await resp.json()  # type: ignore[no-any-return]

    @override
    async def _async_refresh_token(self, token: dict[str, Any]) -> dict[str, Any]:
        """Refresh access token via Keycloak."""
        session = await async_get_bosch_cloud_session(self.hass)
        async with session.post(
            f"{KEYCLOAK_BASE}/token",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
                "refresh_token": token["refresh_token"],
            },
        ) as resp:
            if resp.status >= 400:
                _LOGGER.error("Token refresh failed: HTTP %d", resp.status)
            resp.raise_for_status()
            new_token = await resp.json()
            return {**token, **new_token}


# ── Manual flow helpers (for options re-login) ───────────────────────────────


def _build_auth_url(code_challenge: str, state: str) -> str:
    """Build auth URL for manual re-login (uses bosch.com redirect)."""
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI_MANUAL,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    return f"{KEYCLOAK_BASE}/auth?" + urlencode(params)


def _extract_code(redirect_url: str) -> str | None:
    """Extract the auth code from the pasted redirect URL."""
    url = redirect_url.strip()
    if "?" in url:
        url = url.split("?", 1)[1]
    qs = parse_qs(url)
    if qs.get("error"):
        return None
    codes = qs.get("code")
    return codes[0] if codes else None


async def _exchange_code(
    session: Any, code: str, verifier: str
) -> dict[str, Any] | None:
    """Exchange auth code for tokens (manual flow, bosch.com redirect)."""
    try:
        async with asyncio.timeout(15):
            async with session.post(
                f"{KEYCLOAK_BASE}/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI_MANUAL,
                    "code_verifier": verifier,
                },
            ) as resp:
                if resp.status == 200:
                    return await resp.json()  # type: ignore[no-any-return]
                _LOGGER.warning(
                    "Token exchange HTTP %d: %s",
                    resp.status,
                    (await resp.text())[:200],
                )
    except (TimeoutError, aiohttp.ClientError) as err:
        _LOGGER.warning("Token exchange error: %s", err)
    return None


def _detect_token_client_id(bearer_token: str) -> str | None:
    """Parse a Bosch Keycloak JWT and return the `azp` (authorized party) claim.

    Returns e.g. "oss_residential_app" (new OSS client) or "residential_app"
    (legacy client), or None if the token can't be parsed. Used by the options
    flow to decide whether to show the "migrate to new OAuth client" button.
    """
    if not bearer_token:
        return None
    try:
        parts = bearer_token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return str(payload.get("azp")) if payload.get("azp") is not None else None
    except Exception:
        return None


class RefreshTokenInvalidError(Exception):
    """Keycloak rejected the refresh token (invalid_grant / 400 / 401).

    This is non-recoverable without user interaction — the caller should
    trigger the reauth flow instead of retrying.
    """


class AuthServerOutageError(Exception):
    """Bosch Keycloak auth server returned 5xx — server-side outage.

    The refresh token is probably still valid; retrying later will recover
    once Bosch's infrastructure is back. Caller should NOT trigger the
    reauth flow (nothing for the user to fix) — just back off and retry.
    """


async def _do_refresh(session: Any, refresh_token: str) -> dict[str, Any] | None:
    """Silent renewal via saved refresh_token.

    Returns the token dict on success.
    Returns None on transient client-side failures (network error, timeout)
    — caller may retry.
    Raises RefreshTokenInvalidError on 400/401 (invalid_grant) — caller should
    trigger the reauth flow, retrying is pointless.
    Raises AuthServerOutageError on 5xx — Bosch server is down, retry later
    but do NOT trigger reauth.
    """
    try:
        async with asyncio.timeout(15):
            async with session.post(
                f"{KEYCLOAK_BASE}/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            ) as resp:
                if resp.status == 200:
                    return await resp.json()  # type: ignore[no-any-return]
                body = (await resp.text())[:300]
                _LOGGER.warning(
                    "Token refresh HTTP %d — Keycloak response: %s",
                    resp.status,
                    body,
                )
                if resp.status in (400, 401):
                    raise RefreshTokenInvalidError(
                        f"Keycloak HTTP {resp.status}: {body}"
                    )
                if 500 <= resp.status < 600:
                    raise AuthServerOutageError(f"Bosch Keycloak HTTP {resp.status}")
    except (TimeoutError, aiohttp.ClientError) as err:
        _LOGGER.warning("Token refresh error: %s", err)
    return None


# ─────────────────────────────────────────────────────────────────────────────
class BoschCameraConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle the initial setup flow — automatic OAuth2 PKCE browser login."""

    DOMAIN = DOMAIN
    VERSION = 3

    def __init__(self) -> None:
        super().__init__()
        self._manual_verifier: str | None = None
        self._manual_auth_url: str = ""

    @property
    @override
    def logger(self) -> logging.Logger:
        return _LOGGER

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user pick a login method (the OAuth2 implementation itself
        is supplied by HA-core's application_credentials platform).

        Offers a manual copy/paste fallback (mirrors the options-flow relogin
        path) alongside the automatic browser redirect: SingleKey ID's
        multi-hop redirect chain combined with the my.home-assistant.io relay
        (which tracks "last visited instance" client-side rather than being
        tied to this flow's tab) can strand the automatic flow in the wrong
        tab/webview — reported for the HA Companion App and desktop Safari
        alike (Bosch community PM from SebastianHarder, 2026-07-05).

        NOTE: this used to call `async_register_implementation()` here on
        every flow start. That registered a SECOND, differently-keyed
        implementation alongside the one now supplied by
        `application_credentials.py`, which would make
        `AbstractOAuth2FlowHandler.async_step_pick_implementation` see two
        implementations instead of one and break its single-implementation
        auto-pick fast path. Registration itself now happens exclusively via
        the application_credentials provider — but importing the default
        CREDENTIAL still has to happen here too (not just in `async_setup()`)
        — see the module docstring's "application_credentials" section for
        why a fresh (never-configured) install would otherwise reach
        `auto_login` with zero credentials registered.
        """
        # Only enforce unique_id uniqueness on fresh setup. Reauth + reconfigure
        # both reuse the existing entry.
        if self.source not in (
            config_entries.SOURCE_REAUTH,
            config_entries.SOURCE_RECONFIGURE,
        ):
            await self.async_set_unique_id(DOMAIN)
            # reload_on_update=False: combining a reloading config-flow method
            # with our options update-listener is deprecated in HA 2026.6
            # (error from 2026.12). We keep the listener (it guards options-only
            # reloads); this fresh-setup abort never needs to reload anyway.
            self._abort_if_unique_id_configured(reload_on_update=False)

        # Idempotent — see module docstring. Must run here (not only in
        # __init__.py's async_setup()) so a brand-new install has a
        # credential registered before async_step_auto_login's
        # pick_implementation lookup runs.
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(CLIENT_ID, CLIENT_SECRET, name="Bosch SingleKey ID"),
        )

        return self.async_show_menu(
            step_id="user",
            menu_options=["auto_login", "manual_login"],
        )

    async def async_step_auto_login(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Automatic browser login — the pre-existing OAuth2 PKCE flow, unchanged."""
        return await super().async_step_user(user_input)

    async def async_step_manual_login(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the SingleKey ID login URL as a copy/paste fallback (step 1 of 2)."""
        if self._manual_verifier is None:
            self._manual_verifier, challenge = _pkce_pair()
            state = _encode_jwt(
                self.hass,
                {"flow_id": self.flow_id, "redirect_uri": REDIRECT_URI_MANUAL},
            )
            self._manual_auth_url = _build_auth_url(challenge, state)

        if user_input is not None:
            return await self.async_step_manual_paste()

        return self.async_show_form(
            step_id="manual_login",
            data_schema=vol.Schema(
                {
                    vol.Optional("login_url", default=self._manual_auth_url): str,
                }
            ),
        )

    async def async_step_manual_paste(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Exchange the pasted redirect URL for tokens (step 2 of 2)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            redirect_url = user_input.get("redirect_url", "").strip()
            code = _extract_code(redirect_url)
            cloud_api_override = user_input.get(
                "diagnostic_cloud_api_override", ""
            ).strip()

            if not code:
                errors["redirect_url"] = "invalid_redirect_url"
            elif cloud_api_override and not cloud_api_override.startswith("https://"):
                errors["diagnostic_cloud_api_override"] = "invalid_cloud_api_override"
            else:
                session = await async_get_bosch_cloud_session(self.hass)
                tokens = await _exchange_code(
                    session, code, self._manual_verifier or ""
                )

                if not tokens or not tokens.get("access_token"):
                    errors["redirect_url"] = "token_exchange_failed"
                else:
                    new_data = {
                        "bearer_token": tokens["access_token"],
                        "refresh_token": tokens.get("refresh_token", ""),
                    }
                    # Advanced diagnostic escape hatch only — NEVER pre-filled with
                    # any specific host. Lets a single account test whether it
                    # authorizes against a different, Bosch-confirmed camera-API
                    # base URL instead of the production default (see 2026-07-06
                    # SebastianHarder investigation: sh:authorization.failed can
                    # mean the account is registered on a different backend
                    # environment than the one this integration talks to).
                    if cloud_api_override:
                        new_data["cloud_api_override"] = cloud_api_override.rstrip("/")
                    if self.source == config_entries.SOURCE_REAUTH:
                        existing = self._get_reauth_entry()
                        self.hass.config_entries.async_update_entry(
                            existing, data={**existing.data, **new_data}
                        )
                        self.hass.config_entries.async_schedule_reload(
                            existing.entry_id
                        )
                        return self.async_abort(reason="reauth_successful")
                    if self.source == config_entries.SOURCE_RECONFIGURE:
                        existing = self._get_reconfigure_entry()
                        self.hass.config_entries.async_update_entry(
                            existing, data={**existing.data, **new_data}
                        )
                        self.hass.config_entries.async_schedule_reload(
                            existing.entry_id
                        )
                        return self.async_abort(reason="reconfigure_successful")
                    return self.async_create_entry(
                        title="Bosch Smart Home Camera", data=new_data
                    )

        return self.async_show_form(
            step_id="manual_paste",
            data_schema=vol.Schema(
                {
                    vol.Required("redirect_url"): str,
                    vol.Optional("diagnostic_cloud_api_override", default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Start a reauth flow triggered by invalid_grant/expired refresh token.

        Shows a confirmation dialog, then offers the same auto/manual login
        choice as initial setup. On success, the existing config entry is
        updated in place — options, entities, and automations are preserved.
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show confirmation, then delegate to the OAuth2 user flow."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """User-initiated reconfiguration (Quality-Scale Gold rule).

        Triggered by clicking "Reconfigure" on the integration card. Same
        OAuth flow as initial setup, but updates the existing entry in place
        — entities, automations, options, FCM/SMB settings all preserved.
        """
        if user_input is None:
            return self.async_show_form(step_id="reconfigure")
        return await self.async_step_user()

    @override
    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle completed OAuth2 flow — create new entry or update existing (reauth/reconfigure)."""
        token_data = data.get("token", {})
        new_data = {
            "bearer_token": token_data.get("access_token", ""),
            "refresh_token": token_data.get("refresh_token", ""),
        }
        # Reauth + reconfigure: update the existing entry in place (keeps
        # options, entities, automations, FCM config, SMB settings — everything).
        # HA 2026.6 deprecates async_update_reload_and_abort when the entry also
        # has an options update-listener (double-reload race; error from
        # 2026.12). We keep the listener (it guards options-only reloads) and
        # switch the flow to async_update_and_abort + an explicit schedule_reload
        # so the refreshed credentials are still applied.
        if self.source == config_entries.SOURCE_REAUTH:
            existing = self._get_reauth_entry()
            self.hass.config_entries.async_update_entry(
                existing, data={**existing.data, **new_data}
            )
            self.hass.config_entries.async_schedule_reload(existing.entry_id)
            return self.async_abort(reason="reauth_successful")
        if self.source == config_entries.SOURCE_RECONFIGURE:
            existing = self._get_reconfigure_entry()
            self.hass.config_entries.async_update_entry(
                existing, data={**existing.data, **new_data}
            )
            self.hass.config_entries.async_schedule_reload(existing.entry_id)
            return self.async_abort(reason="reconfigure_successful")
        return self.async_create_entry(
            title="Bosch Smart Home Camera",
            data=new_data,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: BoschCameraConfigEntry,
    ) -> config_entries.OptionsFlow:
        return BoschCameraOptionsFlow(config_entry)


# ─────────────────────────────────────────────────────────────────────────────
class BoschCameraOptionsFlow(config_entries.OptionsFlow):
    """Handle options: feature toggles + optional re-login."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._verifier: str = ""
        self._auth_url: str = ""
        self._pending_options: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        opts: dict[str, Any] = dict(DEFAULT_OPTIONS)
        opts.update(self._config_entry.options)

        current_client = _detect_token_client_id(
            self._config_entry.data.get("bearer_token", "")
        )
        is_legacy_client = current_client == "residential_app"

        errors: dict[str, str] = {}
        invalid_allowlist_token = ""

        if user_input is not None:
            # HA's section() helper nests fields under the section key; flatten
            # back to the legacy single-dict shape before any further handling.
            user_input = _flatten_sections(user_input)

            force_relogin = user_input.pop("force_relogin", False)
            migrate_to_oss = user_input.pop("migrate_to_oss_client", False)

            for k in [
                "enable_snapshots",
                "enable_sensors",
                "enable_snapshot_button",
                "enable_binary_sensors",
                "enable_fcm_push",
                "alert_save_snapshots",
                "alert_delete_after_send",
                "mark_events_read",
                "enable_intercom",
                "enable_local_save",
                "enable_smb_upload",
                "enable_nvr",
                "enable_go2rtc",
                "enable_green_it",
                CONF_ENABLE_WEBHOOK_DELIVERY,
                CONF_ENABLE_PTZ_CONTROLS,
                "use_mjpeg_snapshot",
                CONF_DEFER_DIAG_DURING_STREAM,
                CONF_ENABLE_AI_DESCRIPTION,
                CONF_AI_DESCRIBE_ON_MOTION,
                CONF_AI_NOTIFY_INCLUDE_DESCRIPTION,
                "frigate_endpoints_enabled",
            ]:
                if k in user_input:
                    user_input[k] = bool(user_input[k])

            bind_host = str(user_input.get("frigate_bind_host", "")).strip()
            if bind_host:
                try:
                    ipaddress.ip_address(bind_host)
                except ValueError:
                    errors["frigate_bind_host"] = "invalid_ip_address"
            allowlist_raw = str(user_input.get("frigate_ip_allowlist", "")).strip()
            invalid_allowlist_token = ""
            if allowlist_raw:
                for _token in (
                    t.strip() for t in allowlist_raw.split(",") if t.strip()
                ):
                    try:
                        ipaddress.ip_network(_token, strict=False)
                    except ValueError:
                        errors["frigate_ip_allowlist"] = "invalid_ip_allowlist"
                        invalid_allowlist_token = _token
                        break

            webhook_url_raw = str(user_input.get(CONF_WEBHOOK_URL, "")).strip()
            # Scheme is case-insensitive per RFC 3986 — check lowercased but
            # store/keep webhook_url_raw as typed (matches _flatten_sections'
            # merge below, which uses user_input verbatim).
            if webhook_url_raw and not webhook_url_raw.lower().startswith(
                ("http://", "https://")
            ):
                errors[CONF_WEBHOOK_URL] = "invalid_webhook_url"

            if not errors:
                if migrate_to_oss:
                    # Merge submitted changes on top of existing opts so that
                    # suggested_value fields absent from user_input are preserved.
                    merged = {**opts, **user_input}
                    # Persist any other option changes first so they survive reauth
                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        options=merged,
                    )
                    # Use HA's native reauth trigger — scheduled as a task so the
                    # options dialog closes before the reauth flow registers
                    # (prevents UI race with stacked dialogs). async_start_reauth
                    # is a coroutine in HA 2022.7+, so it must be awaited or
                    # wrapped in a task.
                    self.hass.async_create_task(
                        self._config_entry.async_start_reauth(self.hass)
                    )
                    return self.async_abort(reason="migration_started")

                # Merge submitted changes on top of existing opts so that fields
                # using only suggested_value (no default=) that the user did not
                # edit are absent from user_input but still preserved in the saved
                # options dict.  Bug: without this merge, unedited suggested_value
                # fields revert to DEFAULT_OPTIONS defaults on every save.
                merged = {**opts, **user_input}

                # Give the user an immediate (same-request) signal when they
                # just enabled an SMB-dependent feature (SMB event upload or
                # Mini-NVR SMB storage) but the optional `smbprotocol`
                # package isn't installed — otherwise the only feedback was
                # this same Repairs issue appearing on the *next* coordinator
                # tick, potentially minutes later and on a different UI
                # surface (Settings -> Repairs) the user isn't looking at
                # right after saving. Mirrors __init__.py's
                # _refresh_smb_unavailable_issue (same issue_id, so the two
                # checks can never disagree/duplicate — the periodic tick
                # check keeps it accurate afterward, e.g. once smbprotocol
                # becomes available after a restart). Non-blocking: does NOT
                # add to `errors` / prevent the save, since the config is
                # still valid and will start working on its own once the
                # package is available. `self.hass` is guarded because HA's
                # FlowHandler base class defaults it to None until the flow
                # manager attaches a running instance — always set in
                # production, but this keeps the method safe for any caller
                # that exercises async_step_init before that attachment.
                if self.hass is not None:
                    smb_features = smb_dependent_features(merged)
                    if smb_features and not smb_available():
                        ir.async_create_issue(
                            self.hass,
                            DOMAIN,
                            "smb_unavailable",
                            is_fixable=False,
                            is_persistent=False,
                            severity=ir.IssueSeverity.WARNING,
                            translation_key="smb_unavailable",
                            translation_placeholders={
                                "features": " + ".join(smb_features)
                            },
                        )
                    else:
                        ir.async_delete_issue(self.hass, DOMAIN, "smb_unavailable")

                if force_relogin:
                    self._pending_options = merged
                    self._verifier, challenge = _pkce_pair()
                    self._auth_url = _build_auth_url(
                        challenge, secrets.token_urlsafe(16)
                    )
                    return await self.async_step_relogin_show()

                return self.async_create_entry(title="", data=merged)

        has_refresh = bool(self._config_entry.data.get("refresh_token", ""))

        # Build per-section voluptuous schemas. The schema for each block is
        # picked from `_field_schema_for(opts, key)` so a single source of
        # truth (OPTIONS_SECTIONS + this helper) controls both layout AND
        # field-level types.
        sectioned_schema: dict[Any, Any] = {}

        # Polling intervals — open by default (most-touched group).
        sectioned_schema[vol.Required("polling")] = section(
            vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=int(opts.get("scan_interval", 60)),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                    vol.Optional(
                        "interval_status",
                        default=int(opts.get("interval_status", 300)),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                    vol.Optional(
                        "interval_events",
                        default=int(opts.get("interval_events", 300)),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                    vol.Optional(
                        "snapshot_interval",
                        default=int(opts.get("snapshot_interval", 1800)),
                    ): vol.All(vol.Coerce(int), vol.Range(min=300, max=86400)),
                }
            ),
            {"collapsed": False},
        )

        sectioned_schema[vol.Required("features")] = section(
            vol.Schema(
                {
                    vol.Optional(
                        "enable_snapshots",
                        default=bool(opts.get("enable_snapshots", True)),
                    ): bool,
                    vol.Optional(
                        "enable_sensors",
                        default=bool(opts.get("enable_sensors", True)),
                    ): bool,
                    vol.Optional(
                        "enable_binary_sensors",
                        default=bool(opts.get("enable_binary_sensors", True)),
                    ): bool,
                    vol.Optional(
                        "motion_active_window",
                        default=int(
                            opts.get(
                                "motion_active_window", DEFAULT_MOTION_ACTIVE_WINDOW
                            )
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MOTION_ACTIVE_WINDOW_MIN,
                            max=MOTION_ACTIVE_WINDOW_MAX,
                            step=5,
                            mode=NumberSelectorMode.SLIDER,
                            unit_of_measurement="s",
                        )
                    ),
                    vol.Optional(
                        "enable_snapshot_button",
                        default=bool(opts.get("enable_snapshot_button", True)),
                    ): bool,
                    vol.Optional(
                        "enable_intercom",
                        default=bool(opts.get("enable_intercom", False)),
                    ): bool,
                    vol.Optional(
                        "auto_play_default",
                        default=str(opts.get("auto_play_default", "lan")),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value="lan",
                                    label="LAN auto-play, tap-to-reveal on remote",
                                ),
                                SelectOptionDict(
                                    value="always", label="Always auto-play"
                                ),
                                SelectOptionDict(
                                    value="never",
                                    label="Tap-to-reveal in every session",
                                ),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            {"collapsed": False},
        )

        sectioned_schema[vol.Required("stream")] = section(
            vol.Schema(
                {
                    vol.Optional(
                        "stream_connection_type",
                        default=str(opts.get("stream_connection_type", "local")),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value="auto", label="Auto (Lokal → Cloud Fallback)"
                                ),
                                SelectOptionDict(
                                    value="local", label="Nur Lokal (LAN direkt)"
                                ),
                                SelectOptionDict(
                                    value="remote", label="Nur Cloud (Bosch Proxy)"
                                ),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "live_buffer_mode",
                        default=str(opts.get("live_buffer_mode", "balanced")),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value="latency",
                                    label="Latenz (geringe Verzögerung, kann ruckeln)",
                                ),
                                SelectOptionDict(
                                    value="balanced", label="Ausgewogen (Standard)"
                                ),
                                SelectOptionDict(
                                    value="stable",
                                    label="Stabil (kein Ruckeln, mehr Verzögerung)",
                                ),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "enable_go2rtc",
                        default=bool(opts.get("enable_go2rtc", True)),
                    ): bool,
                    vol.Optional(
                        "enable_green_it",
                        default=bool(opts.get("enable_green_it", False)),
                    ): bool,
                    vol.Optional(
                        "use_mjpeg_snapshot",
                        default=bool(opts.get("use_mjpeg_snapshot", False)),
                    ): bool,
                    vol.Optional(
                        CONF_DEFER_DIAG_DURING_STREAM,
                        default=bool(
                            opts.get(
                                CONF_DEFER_DIAG_DURING_STREAM,
                                DEFAULT_DEFER_DIAG_DURING_STREAM,
                            )
                        ),
                    ): bool,
                }
            ),
            {"collapsed": True},
        )

        sectioned_schema[vol.Required("fcm")] = section(
            vol.Schema(
                {
                    vol.Optional(
                        "enable_fcm_push",
                        default=bool(opts.get("enable_fcm_push", False)),
                    ): bool,
                    vol.Optional(
                        "fcm_push_mode",
                        default=(
                            opts.get("fcm_push_mode", "auto")
                            if opts.get("fcm_push_mode") in ("auto", "polling")
                            else "auto"
                        ),
                    ): vol.In(["auto", "polling"]),
                    vol.Optional(
                        "mark_events_read",
                        default=bool(opts.get("mark_events_read", False)),
                    ): bool,
                    vol.Optional(
                        "alert_save_snapshots",
                        default=bool(opts.get("alert_save_snapshots", False)),
                    ): bool,
                    vol.Optional(
                        "alert_delete_after_send",
                        default=bool(opts.get("alert_delete_after_send", True)),
                    ): bool,
                    vol.Optional(
                        "alert_notify_service",
                        description={
                            "suggested_value": opts.get("alert_notify_service", "")
                        },
                    ): str,
                    vol.Optional(
                        "alert_notify_information",
                        description={
                            "suggested_value": opts.get("alert_notify_information", "")
                        },
                    ): str,
                    vol.Optional(
                        "alert_notify_screenshot",
                        description={
                            "suggested_value": opts.get("alert_notify_screenshot", "")
                        },
                    ): str,
                    vol.Optional(
                        "alert_notify_video",
                        description={
                            "suggested_value": opts.get("alert_notify_video", "")
                        },
                    ): str,
                    vol.Optional(
                        "alert_notify_system",
                        description={
                            "suggested_value": opts.get("alert_notify_system", "")
                        },
                    ): str,
                }
            ),
            {"collapsed": True},
        )

        sectioned_schema[vol.Required("events_storage")] = section(
            vol.Schema(
                {
                    vol.Optional(
                        "folder_pattern",
                        description={
                            "suggested_value": opts.get(
                                "folder_pattern", "{camera}/{year}/{month}/{day}"
                            )
                        },
                    ): str,
                    vol.Optional(
                        "file_pattern",
                        description={
                            "suggested_value": opts.get(
                                "file_pattern", "{camera}_{date}_{time}_{type}_{id}"
                            )
                        },
                    ): str,
                    vol.Optional(
                        "enable_local_save",
                        default=bool(opts.get("enable_local_save", False)),
                    ): bool,
                    vol.Optional(
                        "download_path",
                        description={
                            "suggested_value": opts.get("download_path")
                            or DEFAULT_OPTIONS.get("download_path", "")
                        },
                    ): str,
                    vol.Optional(
                        "enable_smb_upload",
                        default=bool(opts.get("enable_smb_upload", False)),
                    ): bool,
                    vol.Optional(
                        "upload_protocol",
                        default=str(opts.get("upload_protocol", "smb")),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value="smb", label="SMB / CIFS (Standard)"
                                ),
                                SelectOptionDict(
                                    value="ftp",
                                    label="FTP (z.B. FRITZ.NAS — schneller bei vielen Files)",
                                ),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "smb_server",
                        description={"suggested_value": opts.get("smb_server", "")},
                    ): str,
                    vol.Optional(
                        "smb_share",
                        description={"suggested_value": opts.get("smb_share", "")},
                    ): str,
                    vol.Optional(
                        "smb_username",
                        description={"suggested_value": opts.get("smb_username", "")},
                    ): str,
                    vol.Optional(
                        "smb_password",
                        description={"suggested_value": opts.get("smb_password", "")},
                    ): str,
                    vol.Optional(
                        "smb_base_path",
                        description={
                            "suggested_value": opts.get(
                                "smb_base_path", "Bosch-Kameras"
                            )
                        },
                    ): str,
                    vol.Optional(
                        "smb_retention_days",
                        default=int(opts.get("smb_retention_days", 180)),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3650)),
                }
            ),
            {"collapsed": True},
        )

        sectioned_schema[vol.Required("nvr")] = section(
            vol.Schema(
                {
                    vol.Optional(
                        "enable_nvr",
                        default=bool(opts.get("enable_nvr", False)),
                    ): bool,
                    vol.Optional(
                        "nvr_storage_target",
                        default=str(opts.get("nvr_storage_target", "local")),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value="local", label="Lokal (NVR-Ordner)"
                                ),
                                SelectOptionDict(value="smb", label="SMB / CIFS"),
                                SelectOptionDict(value="ftp", label="FTP"),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "nvr_base_path",
                        description={
                            "suggested_value": opts.get(
                                "nvr_base_path", "/config/bosch_nvr"
                            )
                        },
                    ): str,
                    vol.Optional(
                        "nvr_smb_subpath",
                        description={
                            "suggested_value": opts.get("nvr_smb_subpath", "NVR")
                        },
                    ): str,
                    vol.Optional(
                        "nvr_retention_days",
                        default=int(opts.get("nvr_retention_days", 3)),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=365)),
                    vol.Optional(
                        "nvr_quality",
                        default=str(opts.get("nvr_quality", "auto")),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value="auto", label="Auto (max. Qualität, ~30 Mbps)"
                                ),
                                SelectOptionDict(
                                    value="low", label="Niedrig (~1.9 Mbps, LOCAL only)"
                                ),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "nvr_preroll_seconds",
                        default=int(opts.get("nvr_preroll_seconds", 0)),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
                    vol.Optional(
                        "nvr_postroll_seconds",
                        default=int(opts.get("nvr_postroll_seconds", 0)),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
                    vol.Optional(
                        "nvr_preroll_cache_dir",
                        description={
                            "suggested_value": opts.get(
                                "nvr_preroll_cache_dir",
                                "/dev/shm/bosch_nvr_cache",  # noqa: S108 # suggested default shown in UI, user can override via text field
                            )
                        },
                    ): str,
                    vol.Optional(
                        "nvr_finalize_ring_on_event",
                        default=bool(opts.get("nvr_finalize_ring_on_event", False)),
                    ): bool,
                }
            ),
            {"collapsed": True},
        )

        sectioned_schema[vol.Required("webhook")] = section(
            vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_WEBHOOK_DELIVERY,
                        default=bool(opts.get(CONF_ENABLE_WEBHOOK_DELIVERY, False)),
                    ): bool,
                    vol.Optional(
                        CONF_WEBHOOK_URL,
                        description={"suggested_value": opts.get(CONF_WEBHOOK_URL, "")},
                    ): str,
                }
            ),
            {"collapsed": True},
        )

        sectioned_schema[vol.Required("ptz")] = section(
            vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_PTZ_CONTROLS,
                        default=bool(opts.get(CONF_ENABLE_PTZ_CONTROLS, False)),
                    ): bool,
                }
            ),
            {"collapsed": True},
        )

        sectioned_schema[vol.Required("frigate")] = section(
            vol.Schema(
                {
                    vol.Optional(
                        "frigate_endpoints_enabled",
                        default=bool(opts.get("frigate_endpoints_enabled", False)),
                    ): bool,
                    vol.Optional(
                        "frigate_bind_host",
                        default=str(opts.get("frigate_bind_host", "127.0.0.1")),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            # custom_value=True → the two presets are offered, but
                            # the user may also type a specific interface IP
                            # (e.g. 192.168.1.50) to bind to just that NIC.
                            options=[
                                SelectOptionDict(
                                    value="127.0.0.1",
                                    label="Localhost only (127.0.0.1) — default",
                                ),
                                SelectOptionDict(
                                    value="0.0.0.0",  # noqa: S104 # explicit opt-in LAN-exposure choice
                                    label="All LAN interfaces (0.0.0.0) — credential-free, use allowlist/token",
                                ),
                            ],
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "frigate_bind_port",
                        default=int(opts.get("frigate_bind_port", 0)),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
                    vol.Optional(
                        "frigate_ip_allowlist",
                        description={
                            "suggested_value": opts.get("frigate_ip_allowlist", "")
                        },
                    ): str,
                    vol.Optional(
                        "frigate_auth_mode",
                        default=str(opts.get("frigate_auth_mode", "none")),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="none", label="No gate"),
                                SelectOptionDict(
                                    value="path_token",
                                    label="Path token (rtsp://host/<token>/…)",
                                ),
                                SelectOptionDict(
                                    value="basic",
                                    label="RTSP Basic-Auth (rtsp://user:pass@host/…)",
                                ),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "frigate_token",
                        description={"suggested_value": opts.get("frigate_token", "")},
                    ): str,
                    vol.Optional(
                        "frigate_basic_user",
                        default=str(opts.get("frigate_basic_user", "frigate")),
                    ): str,
                    vol.Optional(
                        "frigate_idle_timeout",
                        default=int(opts.get("frigate_idle_timeout", 60)),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
                    vol.Optional(
                        "frigate_max_connections",
                        default=int(opts.get("frigate_max_connections", 8)),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=64,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            {"collapsed": True},
        )

        sectioned_schema[vol.Required("ai")] = section(
            vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_AI_DESCRIPTION,
                        default=bool(opts.get(CONF_ENABLE_AI_DESCRIPTION, False)),
                    ): bool,
                    # Nullable entity picker. The ONLY vol.Any shape HA's
                    # frontend serializer (voluptuous_serialize) accepts is
                    # ``vol.Any(None, <selector>)`` — it emits ``allow_none:
                    # true`` so the frontend submits ``null`` (not ``""``) when
                    # the picker is cleared, and the validator then accepts both
                    # None and a valid entity. The previous ``vol.Any("",
                    # EntitySelector(...))`` ("" first, no None) did NOT match
                    # that shape → "Unable to convert schema: Any(...)" → the
                    # options dialog 500'd on open (issue #35). suggested_value
                    # must be the value or None (never "") so an unset field
                    # round-trips through the nullable contract.
                    vol.Optional(
                        CONF_AI_TASK_ENTITY,
                        description={
                            "suggested_value": opts.get(CONF_AI_TASK_ENTITY) or None
                        },
                    ): vol.Any(
                        None, EntitySelector(EntitySelectorConfig(domain="ai_task"))
                    ),
                    vol.Optional(
                        CONF_AI_DESCRIBE_LANGUAGE,
                        description={
                            "suggested_value": opts.get(
                                CONF_AI_DESCRIBE_LANGUAGE, DEFAULT_AI_DESCRIBE_LANGUAGE
                            )
                        },
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                "Deutsch",
                                "English",
                                "Français",
                                "Italiano",
                                "Español",
                                "Nederlands",
                                "Polski",
                            ],
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_AI_DESCRIBE_PROMPT,
                        description={
                            "suggested_value": opts.get(
                                CONF_AI_DESCRIBE_PROMPT, DEFAULT_AI_DESCRIBE_PROMPT
                            )
                        },
                    ): TextSelector(TextSelectorConfig(multiline=True)),
                    vol.Optional(
                        CONF_AI_DESCRIBE_ON_MOTION,
                        default=bool(opts.get(CONF_AI_DESCRIBE_ON_MOTION, False)),
                    ): bool,
                    vol.Optional(
                        CONF_AI_NOTIFY_INCLUDE_DESCRIPTION,
                        default=bool(
                            opts.get(CONF_AI_NOTIFY_INCLUDE_DESCRIPTION, False)
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_AI_COOLDOWN_SECONDS,
                        default=int(opts.get(CONF_AI_COOLDOWN_SECONDS, 60)),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
                    vol.Optional(
                        CONF_AI_MAX_PER_DAY,
                        default=int(opts.get(CONF_AI_MAX_PER_DAY, 100)),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=0),  # 0 = unlimited; no upper cap
                    ),
                    # Plain text input (HH:MM / HH:MM:SS, empty = disabled). The
                    # backend window parser (_ai_window_allowed) tolerates a
                    # malformed value by disabling the time gate, so format
                    # validation lives there rather than in the schema — a
                    # vol.Any/vol.All wrapper here would break frontend schema
                    # serialization and 500 the options dialog (issue #35).
                    vol.Optional(
                        CONF_AI_ACTIVE_TIME_START,
                        description={
                            "suggested_value": opts.get(CONF_AI_ACTIVE_TIME_START, "")
                        },
                    ): TextSelector(TextSelectorConfig()),
                    # See CONF_AI_ACTIVE_TIME_START above — plain text, validated
                    # by the backend window parser, never wrapped in vol.Any.
                    vol.Optional(
                        CONF_AI_ACTIVE_TIME_END,
                        description={
                            "suggested_value": opts.get(CONF_AI_ACTIVE_TIME_END, "")
                        },
                    ): TextSelector(TextSelectorConfig()),
                    # Nullable entity picker (empty = no condition gate). Same
                    # ``vol.Any(None, <selector>)`` nullable shape as
                    # CONF_AI_TASK_ENTITY above — see that comment for why.
                    vol.Optional(
                        CONF_AI_ACTIVE_CONDITION_ENTITY,
                        description={
                            "suggested_value": opts.get(CONF_AI_ACTIVE_CONDITION_ENTITY)
                            or None
                        },
                    ): vol.Any(None, EntitySelector(EntitySelectorConfig())),
                    vol.Optional(
                        CONF_AI_ACTIVE_CONDITION_STATE,
                        description={
                            "suggested_value": opts.get(
                                CONF_AI_ACTIVE_CONDITION_STATE, "not_home"
                            )
                        },
                    ): TextSelector(TextSelectorConfig()),
                }
            ),
            {"collapsed": True},
        )

        auth_inner: dict[Any, Any] = {
            vol.Optional("force_relogin", default=False): bool,
        }
        if is_legacy_client:
            auth_inner[vol.Optional("migrate_to_oss_client", default=False)] = bool
        sectioned_schema[vol.Required("auth")] = section(
            vol.Schema(auth_inner),
            {"collapsed": True},
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(sectioned_schema),
            errors=errors,
            description_placeholders={
                "token_status": "active (auto-renews)"
                if has_refresh
                else "no refresh token",
                # Pattern-variable literals — without these, formatjs/ICU parses
                # {camera}, {year}, … in the events_storage descriptions as
                # missing variables and renders the whole description blank.
                "camera": "{camera}",
                "year": "{year}",
                "month": "{month}",
                "day": "{day}",
                "type": "{type}",
                "date": "{date}",
                "time": "{time}",
                "id": "{id}",
                # Only populated when frigate_ip_allowlist validation actually
                # fails (Runde2 P3 #8) — empty string is harmless when unused.
                "invalid_allowlist_token": invalid_allowlist_token,
            },
        )

    async def async_step_relogin_show(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show login URL as a pre-filled text field. PKCE already generated in init."""
        if user_input is not None:
            return await self.async_step_relogin_paste()

        return self.async_show_form(
            step_id="relogin_show",
            data_schema=vol.Schema(
                {
                    vol.Optional("login_url", default=self._auth_url): str,
                }
            ),
        )

    async def async_step_relogin_paste(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Paste the redirect URL and exchange for new tokens."""
        errors: dict[str, str] = {}

        if user_input is not None:
            redirect_url = user_input.get("redirect_url", "").strip()
            code = _extract_code(redirect_url)
            cloud_api_override = user_input.get(
                "diagnostic_cloud_api_override", ""
            ).strip()

            if not code:
                errors["redirect_url"] = "invalid_redirect_url"
            elif cloud_api_override and not cloud_api_override.startswith("https://"):
                errors["diagnostic_cloud_api_override"] = "invalid_cloud_api_override"
            else:
                session = await async_get_bosch_cloud_session(self.hass)
                tokens = await _exchange_code(session, code, self._verifier)

                if not tokens or not tokens.get("access_token"):
                    errors["redirect_url"] = "token_exchange_failed"
                else:
                    # Update only the credential data — options are written once
                    # by async_create_entry below.  Writing options here AND via
                    # async_create_entry causes the options-update listener to
                    # fire twice, triggering a double reload.
                    new_data = {
                        **self._config_entry.data,
                        "bearer_token": tokens["access_token"],
                        "refresh_token": tokens.get("refresh_token", ""),
                    }
                    # Advanced diagnostic escape hatch — see manual_paste for
                    # rationale. Only set/overwritten when the user actually
                    # provides a value this time; left untouched otherwise.
                    if cloud_api_override:
                        new_data["cloud_api_override"] = cloud_api_override.rstrip("/")
                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        data=new_data,
                    )
                    _LOGGER.info(
                        "Token re-authenticated successfully — reloading integration"
                    )
                    self.hass.config_entries.async_schedule_reload(
                        self._config_entry.entry_id
                    )
                    return self.async_create_entry(title="", data=self._pending_options)

        return self.async_show_form(
            step_id="relogin_paste",
            data_schema=vol.Schema(
                {
                    vol.Required("redirect_url"): str,
                    vol.Optional("diagnostic_cloud_api_override", default=""): str,
                }
            ),
            errors=errors,
        )
