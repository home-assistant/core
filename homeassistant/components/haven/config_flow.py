"""Config flow for the HAVEN IAQ integration."""

from typing import Any, override

from haveniaq import (
    Capability,
    DeviceInfo,
    HavenApiError,
    HavenClient,
    HavenUnsupportedApiVersionError,
    HavenUnsupportedProductError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_MODEL, DEFAULT_PATH, DEFAULT_PORT, DOMAIN


class HavenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a HAVEN IAQ config flow."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.info: DeviceInfo | None = None

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        path = discovery_info.properties.get(CONF_PATH, DEFAULT_PATH)
        self.data = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_PATH: path,
        }

        try:
            self.info = await self._async_fetch_info(host, port=port, path=path)
        except HavenUnsupportedApiVersionError:
            return self.async_abort(reason="unsupported_api_version")
        except HavenUnsupportedProductError:
            return self.async_abort(reason="unsupported_product")
        except HavenApiError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(self.info.serial_number)
        self._abort_if_unique_id_configured(updates=self.data)

        self.context["title_placeholders"] = {"name": self._entry_title(self.info)}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered HAVEN device."""
        if self.info is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            return self.async_create_entry(
                title=self._entry_title(self.info), data=self.data
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self._entry_title(self.info)},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                info = await self._async_fetch_info(host)
            except HavenUnsupportedApiVersionError:
                errors["base"] = "unsupported_api_version"
            except HavenUnsupportedProductError:
                errors["base"] = "unsupported_product"
            except HavenApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    info.serial_number, raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._entry_title(info),
                    data={
                        CONF_HOST: host,
                        CONF_PORT: DEFAULT_PORT,
                        CONF_PATH: DEFAULT_PATH,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def _async_fetch_info(
        self,
        host: str,
        *,
        port: int = DEFAULT_PORT,
        path: str = DEFAULT_PATH,
    ) -> DeviceInfo:
        session = async_get_clientsession(self.hass)
        client = HavenClient(host, session=session, port=port, path=path)
        info = await client.get_info()
        if not info.supports(Capability.AIR_QUALITY):
            raise HavenUnsupportedProductError(
                "The HAVEN device does not provide air-quality data"
            )
        return info

    @staticmethod
    def _entry_title(info: DeviceInfo) -> str:
        return f"{info.model or DEFAULT_MODEL} {info.serial_number}"
