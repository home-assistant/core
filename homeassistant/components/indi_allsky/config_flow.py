"""Config flow for INDI Allsky integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aioindiallsky import (
    IndiAllSkyAuthError,
    IndiAllSkyClient,
    IndiAllSkyConnectionError,
    IndiAllSkyTimeoutError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN
from .util import get_ssl_context, is_ip_address, normalize_host

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="host",
            ),
        ),
        probatio.Required(CONF_PORT, default=443): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=65535,
                mode=NumberSelectorMode.BOX,
            ),
        ),
        probatio.Optional(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        probatio.Optional(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
        probatio.Optional(CONF_SSL, default=True): BooleanSelector(),
        probatio.Optional(CONF_VERIFY_SSL, default=True): BooleanSelector(),
    }
)

STEP_CREDENTIALS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
    }
)

REAUTH_CONFIRM_SCHEMA = STEP_CREDENTIALS_SCHEMA


async def validate_input(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Validate that the user input allows us to connect to INDI Allsky."""
    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)
    if (username and not password) or (password and not username):
        raise MissingCredentials

    client = IndiAllSkyClient(
        host=data[CONF_HOST],
        port=int(data[CONF_PORT]),
        ssl=get_ssl_context(
            data.get(CONF_SSL, True),
            data.get(CONF_VERIFY_SSL, True),
        ),
        username=username or None,
        password=password or None,
        session=async_get_clientsession(hass),
    )

    try:
        await client.fetch_image("latestimage")
    except IndiAllSkyAuthError as err:
        _LOGGER.error(
            "Authentication failed for INDI Allsky at %s:%s: %s",
            data[CONF_HOST],
            data[CONF_PORT],
            err,
        )
        raise InvalidAuth from err
    except (IndiAllSkyConnectionError, IndiAllSkyTimeoutError) as err:
        _LOGGER.error(
            "Cannot connect to INDI Allsky instance at %s:%s: %s",
            data[CONF_HOST],
            data[CONF_PORT],
            err,
        )
        raise CannotConnect from err
    except Exception as err:
        raise Unknown from err


class IndiAllSkyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for INDI Allsky."""

    VERSION = 1

    _discovered_data: dict[str, Any] | None = None
    _requires_auth: bool = False

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_HOST] = normalize_host(user_input[CONF_HOST])
            user_input[CONF_PORT] = int(user_input[CONF_PORT])
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }
            )

            try:
                await validate_input(self.hass, user_input)
            except MissingCredentials:
                errors["base"] = "missing_credentials"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                port = user_input[CONF_PORT]
                default_port = 443 if user_input.get(CONF_SSL, True) else 80
                host_str = (
                    f"{user_input[CONF_HOST]}:{port}"
                    if port != default_port
                    else user_input[CONF_HOST]
                )
                entry_data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_SSL: user_input.get(CONF_SSL, True),
                    CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, True),
                }
                if user_input.get(CONF_USERNAME):
                    entry_data[CONF_USERNAME] = user_input[CONF_USERNAME]
                if user_input.get(CONF_PASSWORD):
                    entry_data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

                return self.async_create_entry(
                    title=f"INDI Allsky ({host_str})",
                    data=entry_data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of an INDI Allsky server."""
        host = normalize_host(discovery_info.host)
        hostname = normalize_host(discovery_info.hostname)
        ssl = str(discovery_info.properties.get("ssl", "true")).lower() == "true"
        port = discovery_info.port or (443 if ssl else 80)
        mac = discovery_info.properties.get("mac")

        if mac:
            formatted_mac = format_mac(mac)
            current_entry = await self.async_set_unique_id(formatted_mac)
            if current_entry is None:
                for entry in self._async_current_entries(include_ignore=False):
                    if (
                        entry.unique_id is None
                        and normalize_host(entry.data[CONF_HOST]) in (host, hostname)
                        and entry.data[CONF_PORT] == port
                    ):
                        self.hass.config_entries.async_update_entry(
                            entry, unique_id=formatted_mac
                        )
                        current_entry = entry
                        break
            current_host = current_entry.data.get(CONF_HOST) if current_entry else None
            if current_entry and current_entry.data.get(CONF_SSL, True) != ssl:
                return self.async_abort(reason="already_configured")
            updates: dict[str, Any] = {
                CONF_PORT: port,
                CONF_SSL: ssl,
            }
            if not (current_host and not is_ip_address(current_host)):
                updates[CONF_HOST] = host
            self._abort_if_unique_id_configured(updates=updates)
        else:
            for entry in self._async_current_entries(include_ignore=False):
                if (
                    normalize_host(entry.data[CONF_HOST]) in (host, hostname)
                    and entry.data[CONF_PORT] == port
                ):
                    return self.async_abort(reason="already_configured")
            await self._async_handle_discovery_without_unique_id()

        self._discovered_data = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_SSL: ssl,
            CONF_VERIFY_SSL: True,
        }

        server_name = discovery_info.name.split("._")[0]
        self.context["title_placeholders"] = {"name": server_name}

        unverified_ssl_needed = False
        try:
            await validate_input(self.hass, self._discovered_data)
        except InvalidAuth:
            self._requires_auth = True
        except CannotConnect, Unknown:
            if ssl:
                try:
                    unverified_data = {**self._discovered_data, CONF_VERIFY_SSL: False}
                    await validate_input(self.hass, unverified_data)
                except InvalidAuth:
                    self._requires_auth = True
                    unverified_ssl_needed = True
                except CannotConnect, Unknown:
                    return self.async_abort(reason="cannot_connect")
                else:
                    unverified_ssl_needed = True
            else:
                return self.async_abort(reason="cannot_connect")

        if unverified_ssl_needed:
            return await self.async_step_unverified_ssl()

        if self._requires_auth:
            return await self.async_step_credentials()

        return await self.async_step_discovery_confirm()

    def _create_discovered_entry(self) -> ConfigFlowResult:
        """Create a config entry from discovered data."""
        assert self._discovered_data is not None
        self._async_abort_entries_match(
            {
                CONF_HOST: self._discovered_data[CONF_HOST],
                CONF_PORT: self._discovered_data[CONF_PORT],
            }
        )
        port = self._discovered_data[CONF_PORT]
        default_port = 443 if self._discovered_data[CONF_SSL] else 80
        host_str = (
            f"{self._discovered_data[CONF_HOST]}:{port}"
            if port != default_port
            else self._discovered_data[CONF_HOST]
        )
        return self.async_create_entry(
            title=f"INDI Allsky ({host_str})",
            data=self._discovered_data,
        )

    async def async_step_unverified_ssl(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user consent for unverified SSL."""
        if user_input is not None:
            assert self._discovered_data is not None
            self._discovered_data[CONF_VERIFY_SSL] = False
            if self._requires_auth:
                return await self.async_step_credentials()
            return self._create_discovered_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="unverified_ssl",
            description_placeholders=self.context.get("title_placeholders", {}),
        )

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation of discovery."""
        if user_input is not None:
            return self._create_discovered_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=self.context.get("title_placeholders", {}),
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle credentials for a discovered INDI Allsky device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            assert self._discovered_data is not None
            data = {
                **self._discovered_data,
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            try:
                await validate_input(self.hass, data)
            except MissingCredentials:
                errors["base"] = "missing_credentials"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._discovered_data = data
                return self._create_discovered_entry()

        return self.async_show_form(
            step_id="credentials",
            data_schema=STEP_CREDENTIALS_SCHEMA,
            description_placeholders=self.context.get("title_placeholders", {}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication upon auth failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with INDI Allsky credentials."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            validate_data = {**reauth_entry.data, **user_input}
            try:
                await validate_input(self.hass, validate_data)
            except MissingCredentials:
                errors["base"] = "missing_credentials"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )

        suggested_values = dict(user_input or {})
        if CONF_USERNAME not in suggested_values:
            suggested_values[CONF_USERNAME] = reauth_entry.data.get(CONF_USERNAME, "")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_CONFIRM_SCHEMA, suggested_values
            ),
            errors=errors,
        )


class MissingCredentials(HomeAssistantError):
    """Error to indicate one credential field was provided without the other."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class Unknown(HomeAssistantError):
    """Unexpected error."""
