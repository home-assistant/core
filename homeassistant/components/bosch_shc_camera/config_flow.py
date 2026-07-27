"""Config flow for Bosch Smart Home Camera integration.

Setup flow — one-click browser login via Bosch SingleKey ID, using the
my.home-assistant.io redirect for automatic callback.

Options flow:
  Step "init" — feature toggles

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
  `ClientCredential`. The hand-rolled token-refresh logic in
  `token_auth.py` is UNCHANGED — it never went through
  `OAuth2Session`/`AbstractOAuth2Implementation.async_refresh_token` and
  still calls Keycloak directly via `_do_refresh`, using the same
  module-level CLIENT_ID/CLIENT_SECRET constants. Existing config entries
  are unaffected: this integration has never persisted `auth_implementation`
  in entry data (only `bearer_token`/`refresh_token`), so there is nothing
  to migrate.
"""

import asyncio
import base64
from collections.abc import Mapping
import hashlib
import json
import logging
import secrets
from typing import Any, override
from urllib.parse import urlencode

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    AbstractOAuth2Implementation,
    _encode_jwt,
)

from . import DEFAULT_OPTIONS, DOMAIN
from .cloud_ssl import async_get_bosch_cloud_session

# ── Section layout (single source of truth) ───────────────────────────────────
# Sectioned options-flow groups the ~50 fields into collapsible blocks so the
# UI is browsable. The mapping below is consumed both by the section-aware
# schema builder in BoschCameraOptionsFlow.async_step_init AND by
# `_flatten_sections` (round-trip on submit). Adding a field here automatically
# wires it into the right section + flattens correctly on save.
#
# DO NOT add a key to two sections — `_flatten_sections` enforces no-collision.
OPTIONS_SECTIONS: dict[str, list[str]] = {
    "features": [
        "enable_snapshots",
    ],
    "auth": [
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

    for section_key in OPTIONS_SECTIONS:
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
        hass: HomeAssistant,
        client_id: str = CLIENT_ID,
        client_secret: str = CLIENT_SECRET,
        auth_domain: str = DOMAIN,
    ) -> None:
        """Initialize the OAuth2 implementation with the given client credential.

        `auth_domain` identifies WHICH registered application_credentials
        entry this instance was built from (defaults to `DOMAIN` for the
        single auto-imported default credential). Must be distinct per
        credential — `homeassistant.helpers.config_entry_oauth2_flow.
        async_get_implementations` keys its registry by `impl.domain`, so
        two credentials sharing one domain value would make the second
        silently overwrite the first in that registry.
        """
        self.hass = hass
        self._client_id = client_id
        self._client_secret = client_secret
        self._auth_domain = auth_domain
        self._last_verifier: str | None = None

    @property
    @override
    def name(self) -> str:
        """Return the implementation name shown in the UI."""
        return "Bosch SingleKey ID"

    @property
    @override
    def domain(self) -> str:
        """Return the auth_implementation key this credential is registered under."""
        return self._auth_domain

    @property
    def redirect_uri(self) -> str:
        """Return the OAuth2 redirect URI."""
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
                # Do not log the response body — Keycloak error responses can
                # echo token material back in the payload (see token_auth.py).
                _LOGGER.error("Token exchange failed: HTTP %d", resp.status)
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
    except ValueError, TypeError:
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


async def _do_refresh(
    session: Any,
    refresh_token: str,
    client_id: str = CLIENT_ID,
    client_secret: str = CLIENT_SECRET,
) -> dict[str, Any] | None:
    """Silent renewal via saved refresh_token.

    `client_id`/`client_secret` default to the fixed public OSS client but
    should be the credential actually used at login (see
    `token_auth.py::_refresh_token_locked`) — Keycloak rejects a refresh_token
    presented with a different client than the one it was issued to.

    Returns the token dict on success. Returns None when Keycloak responded
    with some other, ambiguous non-2xx/400/401/5xx status (rare/unexpected;
    no basis to call it a confirmed-invalid token).
    Raises TimeoutError/aiohttp.ClientError on a transient network-layer
    failure (timeout, DNS, connection reset) — the caller must retry without
    counting this toward the invalid-grant/reauth escalation, since it
    proves nothing about the refresh token's own validity (bug-hunt
    2026-07-27, Copilot review round 5 — a prior version swallowed these
    into a plain None return, indistinguishable from an ambiguous HTTP
    response).
    Raises RefreshTokenInvalidError on 400/401 (invalid_grant) — caller should
    trigger the reauth flow, retrying is pointless.
    Raises AuthServerOutageError on 5xx — Bosch server is down, retry later
    but do NOT trigger reauth.
    """
    async with asyncio.timeout(15):
        async with session.post(
            f"{KEYCLOAK_BASE}/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        ) as resp:
            if resp.status == 200:
                return await resp.json()  # type: ignore[no-any-return]
            # Do not log or embed the response body in an exception message —
            # Keycloak error responses can echo token material back in the
            # payload (see token_auth.py).
            _LOGGER.warning("Token refresh failed: HTTP %d", resp.status)
            if resp.status in (400, 401):
                raise RefreshTokenInvalidError(f"Keycloak HTTP {resp.status}")
            if 500 <= resp.status < 600:
                raise AuthServerOutageError(f"Bosch Keycloak HTTP {resp.status}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
class BoschCameraConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle the initial setup flow — automatic OAuth2 PKCE browser login."""

    DOMAIN = DOMAIN
    VERSION = 3

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return the logger used by the OAuth2 flow handler base class."""
        return _LOGGER

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Start the automatic browser login.

        The OAuth2 implementation itself is supplied by HA-core's
        application_credentials platform.

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
        # Only enforce unique_id uniqueness on fresh setup. Reauth reuses the
        # existing entry.
        if self.source != config_entries.SOURCE_REAUTH:
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

        return await super().async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
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

    async def _async_verify_camera_access(self, bearer_token: str) -> bool:
        """Verify the freshly-issued token can actually reach the camera API.

        A successful OAuth token exchange only proves SingleKey ID login
        succeeded — Bosch's camera API can still reject a valid token with
        `sh:authorization.failed` for an account whose separate camera
        registration never completed (see camera_list.py's identical
        handling in the coordinator's regular tick). Bronze's
        test-before-configure rule requires catching this before the entry
        is ever created, not after the first coordinator refresh silently
        fails. Returns True (does not block setup) on a timeout/network
        error — a transient hiccup during setup must not be conflated with
        a genuine account-access rejection; the coordinator's own first
        refresh retries and surfaces a clearer error if the problem persists.
        """
        try:
            session = await async_get_bosch_cloud_session(self.hass)
            async with (
                asyncio.timeout(10),
                session.get(
                    f"{CLOUD_API}/v11/video_inputs",
                    headers={
                        "Authorization": f"Bearer {bearer_token}",
                        "Accept": "application/json",
                    },
                ) as resp,
            ):
                if resp.status == 200:
                    return True
                # A 429 (rate limited) or 5xx (Bosch-side outage) is not an
                # account-access denial — it says nothing about whether this
                # account can reach the camera API, only that this one
                # request didn't land. Blocking setup on it would show the
                # misleading "registration incomplete" message for what's
                # really just a transient Bosch-side condition (bug-hunt
                # 2026-07-27, Copilot review round 5).
                if resp.status == 429 or 500 <= resp.status < 600:
                    _LOGGER.debug(
                        "Camera-access verification got transient HTTP %d — not blocking setup",
                        resp.status,
                    )
                    return True
                return False
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug("Camera-access verification skipped (%s)", err)
            return True

    @override
    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle completed OAuth2 flow — create new entry or update existing (reauth)."""
        token_data = data.get("token", {})
        new_data = {
            "bearer_token": token_data.get("access_token", ""),
            "refresh_token": token_data.get("refresh_token", ""),
            # Persisted so a reactive refresh can look up the SAME credential
            # (client_id/secret) the user actually authenticated with, instead
            # of always assuming the default public OSS client — matters if an
            # admin ever registers a custom credential via Settings →
            # Application Credentials. Was previously discarded entirely.
            "auth_implementation": data.get("auth_implementation", DOMAIN),
        }

        if not await self._async_verify_camera_access(new_data["bearer_token"]):
            return self.async_abort(reason="camera_access_denied")

        # Reauth: update the existing entry in place (keeps options, entities,
        # automations, FCM config, SMB settings — everything).
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
        return self.async_create_entry(
            title="Bosch Smart Home Camera",
            data=new_data,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler for this config entry."""
        return BoschCameraOptionsFlow(config_entry)


# ─────────────────────────────────────────────────────────────────────────────
class BoschCameraOptionsFlow(config_entries.OptionsFlow):
    """Handle options: feature toggles + optional re-login."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow for the given config entry."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the options flow's single init step (sectioned feature toggles)."""
        opts: dict[str, Any] = dict(DEFAULT_OPTIONS)
        opts.update(self._config_entry.options)

        current_client = _detect_token_client_id(
            self._config_entry.data.get("bearer_token", "")
        )
        is_legacy_client = current_client == "residential_app"

        errors: dict[str, str] = {}

        if user_input is not None:
            # HA's section() helper nests fields under the section key; flatten
            # back to the legacy single-dict shape before any further handling.
            user_input = _flatten_sections(user_input)

            migrate_to_oss = user_input.pop("migrate_to_oss_client", False)

            if "enable_snapshots" in user_input:
                user_input["enable_snapshots"] = bool(user_input["enable_snapshots"])

            if not errors:
                # Base the persisted dict on the entry's PREVIOUSLY-persisted
                # options only — NOT `opts` (which also carries DEFAULT_OPTIONS'
                # fixed polling-cadence fields). Every remaining field in this
                # options flow uses `default=` (not `suggested_value`), so
                # `user_input` always contains a value for each one on a full
                # form submission; there is nothing left that needs preserving
                # from a wider merge. Using `opts` here previously wrote
                # scan_interval/interval_status/interval_events/
                # snapshot_interval/stream_connection_type into entry.options
                # on every save even though they have no form field — besides
                # being an appropriate-polling violation, it also permanently
                # froze a saving user onto whatever DEFAULT_OPTIONS happened to
                # be at that moment, ignoring any later default change in code
                # (bug-hunt 2026-07-27, Copilot review).
                if migrate_to_oss:
                    merged = {**dict(self._config_entry.options), **user_input}
                    # Persist any other option changes first so they survive reauth
                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        options=merged,
                    )
                    # Use HA's native reauth trigger. async_start_reauth is a
                    # synchronous @callback that schedules its own task
                    # internally (current HA-core config_entries.py) — call
                    # it directly, do not wrap it in async_create_task.
                    self._config_entry.async_start_reauth(self.hass)
                    return self.async_abort(reason="migration_started")

                merged = {**dict(self._config_entry.options), **user_input}
                return self.async_create_entry(title="", data=merged)

        if errors and user_input is not None:
            # The schema below is built entirely from `opts` (the PERSISTED
            # values) — without this, a single invalid field discarded every
            # other edit in the same submission when the form was
            # redisplayed with the error. Merge what the user just typed on
            # top of the persisted values so the redisplayed form shows
            # their edits, not stale saved state.
            opts.update(user_input)

        has_refresh = bool(self._config_entry.data.get("refresh_token", ""))

        # Build per-section voluptuous schemas. OPTIONS_SECTIONS is the single
        # source of truth for layout; this method controls field-level types.
        sectioned_schema: dict[Any, Any] = {}

        sectioned_schema[vol.Required("features")] = section(
            vol.Schema(
                {
                    vol.Optional(
                        "enable_snapshots",
                        default=bool(opts.get("enable_snapshots", True)),
                    ): bool,
                }
            ),
            {"collapsed": False},
        )

        if is_legacy_client:
            sectioned_schema[vol.Required("auth")] = section(
                vol.Schema(
                    {
                        vol.Optional("migrate_to_oss_client", default=False): bool,
                    }
                ),
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
            },
        )
