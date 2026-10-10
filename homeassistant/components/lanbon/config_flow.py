"""Config flow: manual + mDNS. Token is typed by the user, never taken from TXT."""

from typing import TYPE_CHECKING, Any, override

from aiolanbon import (
    LanbonAuthError,
    LanbonClient,
    LanbonConnectionError,
    LanbonError,
    LanbonTimeoutError,
)
from aiolanbon.discovery import discovered_from_mdns
from aiolanbon.models import GatewayInfo
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_GATEWAY_ID, CONF_SCHEME, DEFAULT_PORT, DOMAIN


class ApiDisabled(Exception):
    """Open Integration master switch is off (api_enabled false)."""


async def _validate(
    hass: HomeAssistant, host: str, port: int, token: str, scheme: str = "http"
) -> GatewayInfo:
    """Fetch gateway info and require Open Integration to be on."""
    session = async_get_clientsession(hass)
    client = LanbonClient(host, port, token, session, scheme=scheme)
    info = await client.get_info()
    if not info.api_enabled:
        raise ApiDisabled
    return info


class LanbonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a LANBON config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._scheme: str = "http"
        self._gateway_id: str = ""
        self._title: str = "LANBON"

    def _placeholders(self) -> dict[str, str]:
        """Placeholders for discovery form text."""
        return {
            "name": self._title,
            "host": self._host or "",
        }

    async def _finish(
        self,
        host: str,
        port: int,
        token: str,
        scheme: str,
        errors: dict[str, str],
        *,
        discovery_update: bool = False,
    ) -> ConfigFlowResult | None:
        try:
            info = await _validate(self.hass, host, port, token, scheme)
        except LanbonAuthError:
            errors["base"] = "invalid_auth"
            return None
        except ApiDisabled:
            errors["base"] = "api_disabled"
            return None
        except (
            LanbonConnectionError,
            LanbonTimeoutError,
            OSError,
            TimeoutError,
        ):
            errors["base"] = "cannot_connect"
            return None
        except LanbonError, ValueError, TypeError:
            errors["base"] = "unknown"
            return None

        gateway_id = info.gateway_id
        if not gateway_id:
            return self.async_abort(reason="missing_unique_id")
        title = info.model or info.manufacturer or "LANBON"
        await self.async_set_unique_id(gateway_id)
        if discovery_update:
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: host, CONF_PORT: port, CONF_SCHEME: scheme}
            )
        else:
            self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=title,
            data={
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_TOKEN: token,
                CONF_SCHEME: scheme,
                CONF_GATEWAY_ID: gateway_id,
            },
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            result = await self._finish(
                user_input[CONF_HOST],
                user_input.get(CONF_PORT, DEFAULT_PORT),
                user_input[CONF_TOKEN],
                user_input.get(CONF_SCHEME, "http"),
                errors,
            )
            if result is not None:
                return result
        schema = probatio.Schema(
            {
                probatio.Required(CONF_HOST, default=self._host or ""): str,
                probatio.Required(CONF_PORT, default=self._port): cv.port,
                probatio.Required(CONF_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery. Token is not read from TXT."""
        gw = discovered_from_mdns(
            discovery_info.host,
            discovery_info.port or DEFAULT_PORT,
            discovery_info.properties or {},
        )
        self._host = gw.host
        self._port = gw.port
        self._scheme = gw.scheme
        self._gateway_id = gw.gateway_id
        self._title = gw.model or gw.series or "LANBON"
        self.context["title_placeholders"] = {"name": self._title}
        if self._gateway_id:
            await self.async_set_unique_id(self._gateway_id)
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_SCHEME: self._scheme,
                }
            )
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to paste the token from the device screen."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if TYPE_CHECKING:
                assert self._host is not None
            result = await self._finish(
                self._host,
                self._port,
                user_input[CONF_TOKEN],
                self._scheme,
                errors,
                discovery_update=True,
            )
            if result is not None:
                return result
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=self._placeholders(),
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )
