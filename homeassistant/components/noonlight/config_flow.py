"""Config, reauth, and options flows for the Noonlight integration."""

import logging
import re
from typing import Any

from noonlight_dispatch import (
    NoonlightAuthError,
    NoonlightClient,
    NoonlightConnectionError,
    NoonlightError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from .const import (
    ALL_NOONLIGHT_SERVICES,
    CONF_ADDRESS,
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_CITY,
    CONF_DEDUPE_SECONDS,
    CONF_DEFAULT_ENTRY_DELAY,
    CONF_ENVIRONMENT,
    CONF_HEARTBEAT_MINUTES,
    CONF_LOCATION_ID,
    CONF_NAME,
    CONF_PHONE,
    CONF_SAFETY_ACK,
    CONF_SERVICES_GRANTED,
    CONF_STATE,
    CONF_ZIP,
    DEFAULT_DEDUPE_SECONDS,
    DEFAULT_ENTRY_DELAY,
    DEFAULT_ENVIRONMENT,
    DEFAULT_HEARTBEAT_MINUTES,
    DOMAIN,
    ENV_CUSTOM,
    ENVIRONMENTS,
    MAX_ENTRY_DELAY,
    MAX_HEARTBEAT_MINUTES,
    MIN_ENTRY_DELAY,
    MIN_HEARTBEAT_MINUTES,
    NON_PRODUCTION_ENVIRONMENTS,
    US_STATE_CODES,
    resolve_base_url,
)

_LOGGER = logging.getLogger(__name__)


def _environment_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=env, label=env) for env in ENVIRONMENTS],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="environment",
        )
    )


def _services_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=svc, label=svc) for svc in ALL_NOONLIGHT_SERVICES
            ],
            mode=SelectSelectorMode.LIST,
            multiple=True,
            translation_key="services_granted",
        )
    )


def _entry_delay_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=MIN_ENTRY_DELAY,
            max=MAX_ENTRY_DELAY,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="s",
        )
    )


def _dedupe_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=0,
            max=3600,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="s",
        )
    )


def _heartbeat_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=MIN_HEARTBEAT_MINUTES,
            max=MAX_HEARTBEAT_MINUTES,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="min",
        )
    )


_E164_RE = re.compile(r"\+\d{8,15}")


def normalize_phone(raw: str) -> str:
    """Normalize a phone number to E.164 (e.g. ``+12025550142``).

    Noonlight rejects non-E.164 numbers, and that failure would otherwise only
    surface at dispatch time — during an emergency. Normalize (and validate)
    up front instead. Accepts common US formats (``(202) 555-0142``,
    ``202-555-0142``, ``2025550142``) and already-internationalized numbers
    (a leading ``+`` is trusted). Raises ``ValueError`` if the input cannot be
    confidently converted.
    """
    stripped = raw.strip()
    digits = re.sub(r"\D", "", stripped)
    if stripped.startswith("+"):
        e164 = f"+{digits}"
    elif len(digits) == 10:
        # Bare NANP number — assume US/Canada (+1).
        e164 = f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        e164 = f"+{digits}"
    else:
        raise ValueError(f"cannot normalize phone number: {raw!r}")
    if not _E164_RE.fullmatch(e164):
        raise ValueError(f"not a valid E.164 number: {e164}")
    return e164


def normalize_state(raw: str) -> str:
    """Normalize a US state to its uppercase 2-letter code (e.g. ``VA``).

    Noonlight only accepts the 2-letter code; ``va`` and ``Virginia`` are both
    rejected. Raises ``ValueError`` for anything not in :data:`US_STATE_CODES`.
    """
    code = raw.strip().upper()
    if code not in US_STATE_CODES:
        raise ValueError(f"unsupported state code: {raw!r}")
    return code


_ZIP_RE = re.compile(r"\d{5}(-\d{4})?")


def normalize_zip(raw: str) -> str:
    """Validate a US ZIP code (``62704`` or ``62704-1234``)."""
    zip_code = raw.strip()
    if not _ZIP_RE.fullmatch(zip_code):
        raise ValueError(f"not a valid US ZIP code: {raw!r}")
    return zip_code


def _normalize_caller(user_input: dict[str, Any]) -> dict[str, str]:
    """Normalize phone/state/ZIP in place; return field->error for failures.

    Shared by the initial caller step and the reconfigure step so both reject
    malformed input the same way, at entry time rather than at dispatch.
    """
    errors: dict[str, str] = {}
    for field, normalizer, error in (
        (CONF_PHONE, normalize_phone, "invalid_phone"),
        (CONF_STATE, normalize_state, "invalid_state"),
        (CONF_ZIP, normalize_zip, "invalid_zip"),
    ):
        try:
            user_input[field] = normalizer(user_input[field])
        except ValueError:
            errors[field] = error
    return errors


def _location_unique_id(environment: str, address: str, zip_code: str) -> str:
    """Build a stable per-property unique id.

    Derived from environment + normalized street address + ZIP so the same
    physical property cannot be added twice, while different properties (even
    sharing one API token) remain distinct.
    """
    return "_".join([slugify(environment), slugify(address), slugify(zip_code)])


def _caller_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Caller/location schema, optionally pre-filled with ``defaults``."""
    d = defaults or {}

    def _req(key: str) -> vol.Marker:
        return vol.Required(key, default=d[key]) if key in d else vol.Required(key)

    return vol.Schema(
        {
            _req(CONF_NAME): str,
            _req(CONF_PHONE): str,
            _req(CONF_ADDRESS): str,
            _req(CONF_CITY): str,
            _req(CONF_STATE): str,
            _req(CONF_ZIP): str,
            vol.Optional(
                CONF_LOCATION_ID,
                description={"suggested_value": d.get(CONF_LOCATION_ID)},
            ): str,
        }
    )


async def _validate_credentials(
    hass: Any, environment: str, base_url: str | None, token: str
) -> None:
    """Probe Noonlight to confirm token + reachability without dispatching.

    A GET against a bogus alarm id has no side effects: a 401 means the token
    is bad, anything else (typically 404) means we are reachable and authorised.
    """
    api = NoonlightClient(
        get_async_client(hass),
        token,
        base_url=resolve_base_url(environment, base_url),
    )
    try:
        await api.get_alarm_status("connection-test")
    except NoonlightAuthError as err:
        raise _InvalidAuth from err
    except NoonlightConnectionError as err:
        raise _CannotConnect from err
    except NoonlightError:
        # Reachable + authorised (e.g. 404 for the bogus id) — good enough.
        return


class _CannotConnect(Exception):
    """Credentials step could not reach Noonlight."""


class _InvalidAuth(Exception):
    """Noonlight rejected the supplied token."""


class NoonlightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Noonlight UI setup flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}
        self._reauth_entry: ConfigEntry | None = None

    # -- credentials / environment -------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1 — credentials and environment."""
        errors: dict[str, str] = {}
        if user_input is not None:
            environment = user_input[CONF_ENVIRONMENT]
            base_url = user_input.get(CONF_BASE_URL) or None
            if environment == ENV_CUSTOM and not base_url:
                errors[CONF_BASE_URL] = "base_url_required"
            else:
                try:
                    await _validate_credentials(
                        self.hass,
                        environment,
                        base_url,
                        user_input[CONF_API_TOKEN],
                    )
                except _InvalidAuth:
                    errors["base"] = "invalid_auth"
                except _CannotConnect:
                    errors["base"] = "cannot_connect"
                else:
                    self._data.update(
                        {
                            CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                            CONF_ENVIRONMENT: environment,
                            CONF_BASE_URL: base_url,
                        }
                    )
                    return await self.async_step_caller()

        schema = vol.Schema(
            {
                vol.Required(CONF_API_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_ENVIRONMENT, default=DEFAULT_ENVIRONMENT
                ): _environment_selector(),
                vol.Optional(CONF_BASE_URL): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    # -- caller info ----------------------------------------------------------

    async def async_step_caller(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2 — caller/location info sent to Noonlight on every dispatch.

        Phone, state, and ZIP are normalized/validated here so malformed input
        is rejected with a clear message at entry time, rather than silently
        failing at dispatch (which Noonlight only rejects then). All fields are
        checked together so the user sees every problem at once.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _normalize_caller(user_input)
            if not errors:
                unique_id = _location_unique_id(
                    self._data[CONF_ENVIRONMENT],
                    user_input[CONF_ADDRESS],
                    user_input[CONF_ZIP],
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                self._data.update(user_input)
                return await self.async_step_defaults()

        return self.async_show_form(
            step_id="caller",
            data_schema=_caller_schema(user_input),
            errors=errors,
        )

    # -- defaults -------------------------------------------------------------

    async def async_step_defaults(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 3 — per-call defaults and which services are granted."""
        if user_input is not None:
            self._options = {
                CONF_DEFAULT_ENTRY_DELAY: int(user_input[CONF_DEFAULT_ENTRY_DELAY]),
                CONF_DEDUPE_SECONDS: int(user_input[CONF_DEDUPE_SECONDS]),
                CONF_SERVICES_GRANTED: user_input[CONF_SERVICES_GRANTED],
            }
            if self._data[CONF_ENVIRONMENT] in NON_PRODUCTION_ENVIRONMENTS:
                # Non-production: no live responders, so skip the disclosure.
                return self._create_entry()
            return await self.async_step_safety()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEFAULT_ENTRY_DELAY, default=DEFAULT_ENTRY_DELAY
                ): _entry_delay_selector(),
                vol.Required(
                    CONF_DEDUPE_SECONDS, default=DEFAULT_DEDUPE_SECONDS
                ): _dedupe_selector(),
                vol.Required(
                    CONF_SERVICES_GRANTED, default=ALL_NOONLIGHT_SERVICES
                ): _services_selector(),
            }
        )
        return self.async_show_form(step_id="defaults", data_schema=schema)

    # -- safety acknowledgment ------------------------------------------------

    async def async_step_safety(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 4 — required disclosure when running against production."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_SAFETY_ACK):
                self._data[CONF_SAFETY_ACK] = True
                return self._create_entry()
            errors["base"] = "safety_ack_required"

        schema = vol.Schema(
            {vol.Required(CONF_SAFETY_ACK, default=False): BooleanSelector()}
        )
        return self.async_show_form(step_id="safety", data_schema=schema, errors=errors)

    @callback
    def _create_entry(self) -> ConfigFlowResult:
        title = self._data[CONF_NAME]
        return self.async_create_entry(
            title=title, data=self._data, options=self._options
        )

    # -- reauth ---------------------------------------------------------------

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Triggered by a 401 — re-collect just the token."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Accept a fresh token without re-entering address/contact."""
        assert self._reauth_entry is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _validate_credentials(
                    self.hass,
                    self._reauth_entry.data[CONF_ENVIRONMENT],
                    self._reauth_entry.data.get(CONF_BASE_URL),
                    user_input[CONF_API_TOKEN],
                )
            except _InvalidAuth:
                errors["base"] = "invalid_auth"
            except _CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                    },
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )

    # -- reconfigure ----------------------------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit caller/location info (incl. site label) without re-adding.

        Caller details are not part of the options flow because they change
        what is sent to responders; reconfigure re-collects and re-validates
        them, then reloads the entry.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _normalize_caller(user_input)
            if not errors:
                unique_id = _location_unique_id(
                    entry.data[CONF_ENVIRONMENT],
                    user_input[CONF_ADDRESS],
                    user_input[CONF_ZIP],
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, **user_input}
                )
            defaults = {**entry.data, **user_input}
        else:
            defaults = dict(entry.data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_caller_schema(defaults),
            errors=errors,
        )

    # -- options --------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> NoonlightOptionsFlow:
        """Return the options flow handler."""
        return NoonlightOptionsFlow(entry)


class NoonlightOptionsFlow(OptionsFlow):
    """Adjust entry delay, dedupe window, and granted services post-setup."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Noonlight options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_DEFAULT_ENTRY_DELAY: int(user_input[CONF_DEFAULT_ENTRY_DELAY]),
                    CONF_DEDUPE_SECONDS: int(user_input[CONF_DEDUPE_SECONDS]),
                    CONF_SERVICES_GRANTED: user_input[CONF_SERVICES_GRANTED],
                    CONF_HEARTBEAT_MINUTES: int(user_input[CONF_HEARTBEAT_MINUTES]),
                },
            )

        opts = self._entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEFAULT_ENTRY_DELAY,
                    default=opts.get(CONF_DEFAULT_ENTRY_DELAY, DEFAULT_ENTRY_DELAY),
                ): _entry_delay_selector(),
                vol.Required(
                    CONF_DEDUPE_SECONDS,
                    default=opts.get(CONF_DEDUPE_SECONDS, DEFAULT_DEDUPE_SECONDS),
                ): _dedupe_selector(),
                vol.Required(
                    CONF_SERVICES_GRANTED,
                    default=opts.get(CONF_SERVICES_GRANTED, ALL_NOONLIGHT_SERVICES),
                ): _services_selector(),
                vol.Required(
                    CONF_HEARTBEAT_MINUTES,
                    default=opts.get(CONF_HEARTBEAT_MINUTES, DEFAULT_HEARTBEAT_MINUTES),
                ): _heartbeat_selector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
