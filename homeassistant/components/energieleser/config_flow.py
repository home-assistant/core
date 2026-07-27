"""Config flow for the energieleser integration."""

from typing import Any, override

from energieleser import (
    EnergieleserClient,
    EnergieleserConnectionError,
    EnergieleserError,
    EnergieleserUnknownDeviceError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_SW_VERSION, DOMAIN, device_model_name

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
    }
)


class EnergieleserConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for energieleser."""

    VERSION = 1

    _discovered_host: str
    _discovered_device_id: str
    _discovered_device_type: str
    _discovered_sw_version: str | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            client = EnergieleserClient(
                host=host, session=async_get_clientsession(self.hass)
            )
            try:
                device = await client.get_device()
            except EnergieleserConnectionError:
                errors["base"] = "cannot_connect"
            except EnergieleserUnknownDeviceError:
                errors["base"] = "unknown_device_type"
            except EnergieleserError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    device.device_id, raise_on_progress=False
                )
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self._create_entry(
                    host, device_model_name(device.device_type), device.device_id
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        client = EnergieleserClient(
            host=host, session=async_get_clientsession(self.hass)
        )

        # The mDNS hostname ("strom-one-123.local.") encodes the API device_id
        # ("STROM_ONE_123"), so it can gate an already-configured device before
        # any network request and refresh the host even while it is unreachable.
        device_id = discovery_info.hostname.split(".")[0].replace("-", "_").upper()
        sw_version = discovery_info.properties.get("version")
        updates: dict[str, Any] = {CONF_HOST: host}
        if sw_version is not None:
            updates[CONF_SW_VERSION] = sw_version

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates=updates)

        try:
            device = await client.get_device()
        except EnergieleserConnectionError:
            return self.async_abort(reason="cannot_connect")
        except EnergieleserUnknownDeviceError:
            return self.async_abort(reason="unknown_device_type")
        except EnergieleserError:
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(device.device_id)
        self._abort_if_unique_id_configured(updates=updates)

        self._discovered_host = host
        self._discovered_device_id = device.device_id
        self._discovered_device_type = device_model_name(device.device_type)
        self._discovered_sw_version = sw_version

        self.context.update(
            {
                "title_placeholders": {
                    "device_id": device.device_id,
                    "device_type": self._discovered_device_type,
                    "host": host,
                },
            }
        )
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle confirmation of a zeroconf-discovered device."""
        if user_input is not None:
            return self._create_entry(
                self._discovered_host,
                self._discovered_device_type,
                self._discovered_device_id,
                self._discovered_sw_version,
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "device_id": self._discovered_device_id,
                "device_type": self._discovered_device_type,
                "host": self._discovered_host,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            client = EnergieleserClient(
                host=host, session=async_get_clientsession(self.hass)
            )
            try:
                device = await client.get_device()
            except EnergieleserConnectionError:
                errors["base"] = "cannot_connect"
            except EnergieleserUnknownDeviceError:
                errors["base"] = "unknown_device_type"
            except EnergieleserError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device.device_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_SCHEMA,
                suggested_values=entry.data | (user_input or {}),
            ),
            errors=errors,
        )

    def _create_entry(
        self, host: str, title: str, device_id: str, sw_version: str | None = None
    ) -> ConfigFlowResult:
        """Create the config entry with a friendly title and consistent data."""
        data: dict[str, Any] = {CONF_HOST: host, CONF_DEVICE_ID: device_id}
        if sw_version is not None:
            data[CONF_SW_VERSION] = sw_version
        return self.async_create_entry(title=title, data=data)
