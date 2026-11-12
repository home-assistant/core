"""Configure a discovered local Elecway storage device."""

from typing import Any, override

from aioelecway import ElecwayError, StorageClient
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN, LOGGER
from .discovery import async_discover, storage_serial_number


class ElecwayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure one entry per storage serial number."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize discovery state."""
        self._devices: dict[str, ZeroconfServiceInfo] = {}
        self._discovery: ZeroconfServiceInfo

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a storage device discovered on the local network."""
        if user_input is not None:
            return await self.async_step_zeroconf(
                self._devices[user_input[CONF_DEVICE]]
            )

        configured = self._async_current_ids(include_ignore=False)
        self._devices = {
            serial: info
            for serial, info in (await async_discover(self.hass)).items()
            if serial not in configured
        }
        if not self._devices:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_DEVICE): probatio.In(
                        {
                            serial: f"{serial} ({info.host})"
                            for serial, info in self._devices.items()
                        }
                    )
                }
            ),
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle only storage announcements and update changed addresses."""
        if not (serial := storage_serial_number(discovery_info.name)):
            return self.async_abort(reason="not_supported")
        if discovery_info.port is None:
            return self.async_abort(reason="not_supported")
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: discovery_info.host, CONF_PORT: discovery_info.port}
        )
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"serial_number": serial}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate a live report before saving the entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            assert self._discovery.port is not None
            client = StorageClient(
                async_get_clientsession(self.hass),
                self._discovery.host,
                self._discovery.port,
                self.unique_id,
            )
            try:
                data = await client.connect()
            except ElecwayError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error validating Elecway storage")
                errors["base"] = "unknown"
            else:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Elecway {data.serial_number}",
                    data={
                        CONF_HOST: self._discovery.host,
                        CONF_PORT: self._discovery.port,
                        CONF_MODEL: data.model,
                    },
                )
            finally:
                await client.disconnect()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"serial_number": self.unique_id or ""},
            errors=errors,
        )
