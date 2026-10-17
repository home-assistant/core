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
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
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
        probatio.Optional(CONF_SSL, default=True): BooleanSelector(),
        probatio.Optional(CONF_VERIFY_SSL, default=True): BooleanSelector(),
    }
)


async def validate_input(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Validate that the user input allows us to connect to INDI Allsky."""
    client = IndiAllSkyClient(
        host=data[CONF_HOST],
        port=int(data[CONF_PORT]),
        ssl=get_ssl_context(
            data.get(CONF_SSL, True),
            data.get(CONF_VERIFY_SSL, True),
        ),
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

    _discovered_data: dict[str, Any]

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
                return self.async_create_entry(
                    title=f"INDI Allsky ({host_str})",
                    data=user_input,
                )

        suggested_values = user_input or getattr(self, "_discovered_data", None)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of an INDI Allsky server."""
        host = normalize_host(discovery_info.host)
        if discovery_info.type == "_http._tcp.local.":
            ssl = False
        elif discovery_info.type == "_https._tcp.local.":
            ssl = True
        elif "ssl" in discovery_info.properties:
            ssl = str(discovery_info.properties["ssl"]).lower() == "true"
        else:
            ssl = True

        port = discovery_info.port or (443 if ssl else 80)
        mac = discovery_info.properties.get("mac")

        if mac:
            formatted_mac = format_mac(mac)
            current_entry = await self.async_set_unique_id(formatted_mac)
            current_host = current_entry.data.get(CONF_HOST) if current_entry else None
            updates: dict[str, Any] = {
                CONF_PORT: port,
                CONF_SSL: ssl,
            }
            if not (current_host and not is_ip_address(current_host)):
                updates[CONF_HOST] = host
            self._abort_if_unique_id_configured(updates=updates)
        else:
            self._async_abort_entries_match(
                {
                    CONF_HOST: host,
                    CONF_PORT: port,
                }
            )
            await self._async_handle_discovery_without_unique_id()

        self._discovered_data = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_SSL: ssl,
            CONF_VERIFY_SSL: True,
        }

        try:
            await validate_input(self.hass, self._discovered_data)
        except CannotConnect, InvalidAuth:
            return await self.async_step_user()
        except Unknown:
            return self.async_abort(reason="unknown")

        server_name = discovery_info.name.split("._")[0]
        self.context["title_placeholders"] = {"name": server_name}

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation of discovery."""
        if user_input is not None:
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

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=self.context.get("title_placeholders", {}),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class Unknown(HomeAssistantError):
    """Unexpected error."""
