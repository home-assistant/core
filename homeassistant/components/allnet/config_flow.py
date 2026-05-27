"""Config flow for ALLNET."""

from collections.abc import Mapping
import logging
from typing import Any

from allnet import AllnetClient
from allnet.exceptions import (
    AllnetAuthenticationError,
    AllnetConnectionError,
    AllnetInvalidResponseError,
    AllnetUnsupportedFirmwareError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_DEVICE_PROFILE,
    CONF_USE_SSL,
    DEFAULT_DEVICE_PROFILE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USE_SSL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_PROFILE_OPTIONS = [
    SelectOptionDict(value="auto", label="auto"),
    SelectOptionDict(value="msr", label="msr"),
    SelectOptionDict(value="managed_switch", label="managed_switch"),
]

_PROFILE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=DEVICE_PROFILE_OPTIONS,
        mode=SelectSelectorMode.LIST,
        translation_key="device_profile",
    )
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_USE_SSL, default=DEFAULT_USE_SSL): bool,
        vol.Optional(
            CONF_DEVICE_PROFILE, default=DEFAULT_DEVICE_PROFILE
        ): _PROFILE_SELECTOR,
    }
)

STEP_ZEROCONF_CONFIRM_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(
            CONF_DEVICE_PROFILE, default=DEFAULT_DEVICE_PROFILE
        ): _PROFILE_SELECTOR,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


async def _validate_and_get_unique_id(
    hass,
    host: str,
    username: str | None,
    password: str | None,
    use_ssl: bool,
) -> tuple[str, str]:
    """Validate connection and return (unique_id, device_name). Raises on error."""
    session = async_get_clientsession(hass)
    client = AllnetClient(
        host=host,
        username=username or None,
        password=password or None,
        use_ssl=use_ssl,
        session=session,
        timeout=10.0,
    )
    try:
        device_info = await client.async_get_device_info()
    finally:
        # session is HA-managed, no need to close client separately
        pass

    return device_info.unique_id, device_info.name or device_info.model or host


class AllnetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an ALLNET config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            username = user_input.get(CONF_USERNAME, "").strip() or None
            password = user_input.get(CONF_PASSWORD, "") or None
            use_ssl = user_input.get(CONF_USE_SSL, DEFAULT_USE_SSL)

            try:
                unique_id, name = await _validate_and_get_unique_id(
                    self.hass, host, username, password, use_ssl
                )
            except AllnetAuthenticationError:
                errors["base"] = "invalid_auth"
            except AllnetUnsupportedFirmwareError:
                errors["base"] = "unsupported_firmware"
            except AllnetConnectionError:
                errors["base"] = "cannot_connect"
            except AllnetInvalidResponseError:
                _LOGGER.exception("Unexpected error connecting to %s", host)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                data = {
                    CONF_HOST: host,
                    CONF_USE_SSL: use_ssl,
                }
                if username:
                    data[CONF_USERNAME] = username
                if password:
                    data[CONF_PASSWORD] = password
                if user_input.get(CONF_DEVICE_PROFILE):
                    data[CONF_DEVICE_PROFILE] = user_input[CONF_DEVICE_PROFILE]
                return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a Zeroconf discovery."""
        host = discovery_info.host
        name = discovery_info.name.removesuffix("._http._tcp.local.")

        # Filter: only accept instance names starting with "all" (e.g. "all3500")
        if not name.lower().startswith("all"):
            return self.async_abort(reason="not_allnet_device")

        self._discovered_host = host
        self._discovered_name = name

        # Check if already configured at this host
        await self.async_set_unique_id(None)  # reset; will be set after validation
        self._abort_if_unique_id_configured()

        # Quick pre-validation: is the JSON API accessible?
        try:
            unique_id, device_name = await _validate_and_get_unique_id(
                self.hass, host, None, None, False
            )
        except AllnetAuthenticationError:
            # Auth required — still show confirmation, user will enter credentials
            pass
        except (
            AllnetConnectionError,
            AllnetUnsupportedFirmwareError,
            AllnetInvalidResponseError,
        ):
            return self.async_abort(reason="cannot_connect")
        else:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
            self._discovered_name = device_name

        self.context["title_placeholders"] = {
            "name": self._discovered_name or name,
            "host": host,
        }

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=STEP_ZEROCONF_CONFIRM_SCHEMA,
            description_placeholders={
                "name": self._discovered_name or name,
                "host": host,
            },
        )

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Zeroconf confirmation."""
        errors: dict[str, str] = {}
        host = self._discovered_host or ""

        if user_input is not None:
            username = user_input.get(CONF_USERNAME, "").strip() or None
            password = user_input.get(CONF_PASSWORD, "") or None

            try:
                unique_id, name = await _validate_and_get_unique_id(
                    self.hass, host, username, password, False
                )
            except AllnetAuthenticationError:
                errors["base"] = "invalid_auth"
            except AllnetUnsupportedFirmwareError:
                errors["base"] = "unsupported_firmware"
            except AllnetConnectionError, AllnetInvalidResponseError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                data: dict[str, Any] = {CONF_HOST: host, CONF_USE_SSL: False}
                if username:
                    data[CONF_USERNAME] = username
                if password:
                    data[CONF_PASSWORD] = password
                if user_input.get(CONF_DEVICE_PROFILE):
                    data[CONF_DEVICE_PROFILE] = user_input[CONF_DEVICE_PROFILE]
                return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=STEP_ZEROCONF_CONFIRM_SCHEMA,
            description_placeholders={
                "name": self._discovered_name or host,
                "host": host,
            },
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication initiation."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry
        host = entry.data.get(CONF_HOST, "") if entry else ""

        if user_input is not None and entry is not None:
            username = user_input.get(CONF_USERNAME, "").strip() or None
            password = user_input.get(CONF_PASSWORD, "") or None
            use_ssl = entry.data.get(CONF_USE_SSL, DEFAULT_USE_SSL)

            try:
                await _validate_and_get_unique_id(
                    self.hass, host, username, password, use_ssl
                )
            except AllnetAuthenticationError:
                errors["base"] = "invalid_auth"
            except AllnetConnectionError, AllnetInvalidResponseError:
                errors["base"] = "cannot_connect"
            else:
                new_data = {**entry.data}
                if username:
                    new_data[CONF_USERNAME] = username
                else:
                    new_data.pop(CONF_USERNAME, None)
                if password:
                    new_data[CONF_PASSWORD] = password
                else:
                    new_data.pop(CONF_PASSWORD, None)
                self.hass.config_entries.async_update_entry(entry, data=new_data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            description_placeholders={"host": host},
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AllnetOptionsFlow:
        """Return the options flow handler."""
        return AllnetOptionsFlow(config_entry)


class AllnetOptionsFlow(config_entries.OptionsFlow):
    """Handle ALLNET options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): vol.All(
                        int,
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
        )
