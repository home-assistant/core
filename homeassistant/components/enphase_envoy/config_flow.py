"""Config flow for Enphase Envoy integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from awesomeversion import AwesomeVersion
import jwt
from pyenphase import AUTH_TOKEN_MIN_VERSION, Envoy, EnvoyError, EnvoyTokenAuth
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.helpers.typing import VolDictType
from homeassistant.util import dt as dt_util

from .const import (
    ACCESS_TOKEN_LOGIN_URL,
    CONF_MANUAL_TOKEN,
    DOMAIN,
    INVALID_AUTH_ERRORS,
    OPTION_DIAGNOSTICS_INCLUDE_FIXTURES,
    OPTION_DIAGNOSTICS_INCLUDE_FIXTURES_DEFAULT_VALUE,
    OPTION_DISABLE_KEEP_ALIVE,
    OPTION_DISABLE_KEEP_ALIVE_DEFAULT_VALUE,
)
from .coordinator import EnphaseConfigEntry

_LOGGER = logging.getLogger(__name__)

ENVOY = "Envoy"

CONF_SERIAL = "serial"

INSTALLER_AUTH_USERNAME = "installer"


def token_lifetime(token: str) -> int:
    """Return token lifetime in days."""
    days_left = 0
    try:
        jwt_payload = jwt.decode(token, options={"verify_signature": False})
        exp = jwt_payload.get("exp")
        if exp is not None:
            days_left = int((int(exp) - dt_util.utcnow().timestamp()) / 86400)
    except jwt.PyJWTError, KeyError, TypeError, ValueError:
        days_left = 0
    return days_left


def descriptions(serial: str, token: str = "") -> dict[str, str]:
    """Build description placeholders."""
    return {
        CONF_SERIAL: serial,
        "enphase_url": ACCESS_TOKEN_LOGIN_URL,
        "token_life": str(token_lifetime(token)) if token else "?",
    }


async def validate_input(
    hass: HomeAssistant,
    host: str,
    username: str,
    password: str,
    token: str | None,
    errors: dict[str, str],
    description_placeholders: dict[str, str],
) -> Envoy:
    """Validate the user input allows us to connect."""
    envoy = Envoy(host, async_get_clientsession(hass, verify_ssl=False))
    try:
        await envoy.setup()
        await envoy.authenticate(username=username, password=password, token=token)
    except INVALID_AUTH_ERRORS as e:
        errors["base"] = "invalid_auth"
        description_placeholders["reason"] = str(e)
    except EnvoyError as e:
        errors["base"] = "cannot_connect"
        description_placeholders["reason"] = str(e)
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"

    return envoy


class EnphaseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Enphase Envoy."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize an envoy flow."""
        self.ip_address: str | None = None
        self.username = None
        self.protovers: str | None = None
        self.manual_token: bool = False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: EnphaseConfigEntry,
    ) -> EnvoyOptionsFlowHandler:
        """Options flow handler for Enphase_Envoy."""
        return EnvoyOptionsFlowHandler()

    @callback
    def _async_generate_schema(self) -> vol.Schema:
        """Generate schema."""
        schema: VolDictType = {}

        if self.ip_address:
            schema[vol.Required(CONF_HOST, default=self.ip_address)] = vol.In(
                [self.ip_address]
            )
        elif self.source != SOURCE_REAUTH:
            schema[vol.Required(CONF_HOST)] = str

        default_username = ""
        if (
            not self.username
            and self.protovers
            and AwesomeVersion(self.protovers) < AUTH_TOKEN_MIN_VERSION
        ):
            default_username = INSTALLER_AUTH_USERNAME

        if self.manual_token:
            # in manual token entry mode show token input field
            schema[vol.Optional(CONF_TOKEN, default="")] = str
        else:
            # in automatic token mode show username and password inputs
            schema[
                vol.Optional(CONF_USERNAME, default=self.username or default_username)
            ] = str
            schema[vol.Optional(CONF_PASSWORD, default="")] = str

        # option to switch between automatic and manual token entry modes
        schema[vol.Optional(CONF_MANUAL_TOKEN, default=self.manual_token)] = bool

        return vol.Schema(schema)

    @callback
    def _async_current_hosts(self) -> set[str]:
        """Return a set of hosts."""
        return {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_HOST in entry.data
        }

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        if _LOGGER.isEnabledFor(logging.DEBUG):
            current_hosts = self._async_current_hosts()
            _LOGGER.debug(
                "Zeroconf ip %s processing %s, current hosts: %s",
                discovery_info.ip_address.version,
                discovery_info.host,
                current_hosts,
            )
        if discovery_info.ip_address.version != 4:
            return self.async_abort(reason="not_ipv4_address")
        serial = discovery_info.properties["serialnum"]
        self.protovers = discovery_info.properties.get("protovers")
        await self.async_set_unique_id(serial)
        self.ip_address = discovery_info.host
        self._abort_if_unique_id_configured({CONF_HOST: self.ip_address})
        _LOGGER.debug(
            "Zeroconf ip %s, fw %s, no existing entry with serial %s",
            self.ip_address,
            self.protovers,
            serial,
        )
        for entry in self._async_current_entries(include_ignore=False):
            if (
                entry.unique_id is None
                and CONF_HOST in entry.data
                and entry.data[CONF_HOST] == self.ip_address
            ):
                _LOGGER.debug(
                    "Zeroconf update envoy with this ip and blank unique_id",
                )
                # Found an entry with blank unique_id (prior deleted) with same ip
                # If the title is still default shorthand 'Envoy' then append serial
                # to differentiate multiple Envoy. Don't change the title if any other
                # title is still present in the old entry.
                title = f"{ENVOY} {serial}" if entry.title == ENVOY else entry.title
                return self.async_update_reload_and_abort(
                    entry, title=title, unique_id=serial, reason="already_configured"
                )

        _LOGGER.debug("Zeroconf ip %s to step user", self.ip_address)
        return await self.async_step_user()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is None:
            # remember current manual_token setting to detect switch between modes
            self.manual_token = reauth_entry.data.get(CONF_MANUAL_TOKEN, False)
            token = reauth_entry.data.get(CONF_TOKEN, "")
        elif user_input.get(CONF_MANUAL_TOKEN) != self.manual_token:
            # user is switching between manual and automatic token entry mode
            # display the form in the other mode, no configuration update yet
            self.manual_token = user_input[CONF_MANUAL_TOKEN]
            token = user_input.get(CONF_TOKEN, "")
        else:
            envoy = await validate_input(
                self.hass,
                reauth_entry.data[CONF_HOST],
                user_input.get(CONF_USERNAME, ""),
                user_input.get(CONF_PASSWORD, ""),
                token := user_input.get(CONF_TOKEN, ""),
                errors,
                description_placeholders,
            )
            if not errors:
                # successful authentication, update config
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input
                    | (
                        {CONF_TOKEN: envoy.auth.token}
                        if isinstance(envoy.auth, EnvoyTokenAuth)
                        else {}
                    ),
                )

        serial = reauth_entry.unique_id or "-"
        self.context["title_placeholders"] = {
            CONF_SERIAL: serial,
            CONF_HOST: reauth_entry.data[CONF_HOST],
        }
        description_placeholders.update(descriptions(serial, token))
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                self._async_generate_schema(),
                user_input or reauth_entry.data,
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    def _async_envoy_name(self) -> str:
        """Return the name of the envoy."""
        return f"{ENVOY} {self.unique_id}" if self.unique_id else ENVOY

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        host = (user_input or {}).get(CONF_HOST) or self.ip_address or ""

        token = ""
        if user_input is not None:
            if (
                manual_mode := user_input.get(CONF_MANUAL_TOKEN, False)
            ) != self.manual_token:
                # for new config self.manual_token starts default as false
                # user is switching between manual and automatic token entry mode
                # show form again in other mode, no configuration update yet
                self.manual_token = manual_mode
                token = user_input.get(CONF_TOKEN, "")
            else:
                envoy = await validate_input(
                    self.hass,
                    host,
                    user_input.get(CONF_USERNAME, ""),
                    user_input.get(CONF_PASSWORD, ""),
                    token := user_input.get(CONF_TOKEN, ""),
                    errors,
                    description_placeholders,
                )
                if not errors:
                    name = self._async_envoy_name()
                    # successful authentication, store token in config
                    token_update = (
                        {CONF_TOKEN: envoy.auth.token}
                        if isinstance(envoy.auth, EnvoyTokenAuth)
                        else {}
                    )

                    if not self.unique_id:
                        await self.async_set_unique_id(envoy.serial_number)
                        name = self._async_envoy_name()

                    if self.unique_id:
                        # If envoy exists in configuration update fields and exit
                        self._abort_if_unique_id_configured(
                            {
                                CONF_HOST: host,
                                CONF_USERNAME: user_input.get(CONF_USERNAME, ""),
                                CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                                CONF_MANUAL_TOKEN: self.manual_token,
                            }
                            | token_update,
                            error="reauth_successful",
                        )

                    # CONF_NAME is still set for legacy backwards compatibility
                    return self.async_create_entry(
                        title=name, data={CONF_NAME: name} | user_input | token_update
                    )

        if self.unique_id:
            self.context["title_placeholders"] = {
                CONF_SERIAL: self.unique_id,
                CONF_HOST: host,
            }
        description_placeholders.update(descriptions("", token))
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                self._async_generate_schema(),
                user_input or {},
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add reconfigure step to allow to manually reconfigure a config entry."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is None:
            # remember current manual_token setting to detect switch between modes
            self.manual_token = reconfigure_entry.data.get(CONF_MANUAL_TOKEN, False)
            token = reconfigure_entry.data.get(CONF_TOKEN, "")
        elif user_input.get(CONF_MANUAL_TOKEN) != self.manual_token:
            # user switches between manual and automatic token entry mode
            # show form again on other mode, no configuration update yet
            self.manual_token = user_input[CONF_MANUAL_TOKEN]
            token = user_input.get(CONF_TOKEN, "")
        else:
            envoy = await validate_input(
                self.hass,
                host := user_input[CONF_HOST],
                username := user_input.get(CONF_USERNAME, ""),
                password := user_input.get(CONF_PASSWORD, ""),
                token := user_input.get(CONF_TOKEN, ""),
                errors,
                description_placeholders,
            )
            if not errors:
                # successful authentication, store token in config
                await self.async_set_unique_id(envoy.serial_number)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_MANUAL_TOKEN: self.manual_token,
                    }
                    | (
                        {CONF_TOKEN: envoy.auth.token}
                        if isinstance(envoy.auth, EnvoyTokenAuth)
                        else {}
                    ),
                )

        serial = reconfigure_entry.unique_id or "-"
        self.context["title_placeholders"] = {
            CONF_SERIAL: serial,
            CONF_HOST: reconfigure_entry.data[CONF_HOST],
        }
        description_placeholders.update(descriptions(serial, token))
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                self._async_generate_schema(),
                user_input or reconfigure_entry.data,
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )


class EnvoyOptionsFlowHandler(OptionsFlowWithReload):
    """Envoy config flow options handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        if TYPE_CHECKING:
            assert self.config_entry.unique_id is not None

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        OPTION_DIAGNOSTICS_INCLUDE_FIXTURES,
                        default=self.config_entry.options.get(
                            OPTION_DIAGNOSTICS_INCLUDE_FIXTURES,
                            OPTION_DIAGNOSTICS_INCLUDE_FIXTURES_DEFAULT_VALUE,
                        ),
                    ): bool,
                    vol.Required(
                        OPTION_DISABLE_KEEP_ALIVE,
                        default=self.config_entry.options.get(
                            OPTION_DISABLE_KEEP_ALIVE,
                            OPTION_DISABLE_KEEP_ALIVE_DEFAULT_VALUE,
                        ),
                    ): bool,
                }
            ),
            description_placeholders={
                CONF_SERIAL: self.config_entry.unique_id,
                CONF_HOST: self.config_entry.data[CONF_HOST],
            },
        )
