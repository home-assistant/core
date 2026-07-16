"""Config flow for LinknLink."""

from typing import Any, override

from aiolinknlink import UltraClient, UltraError, UltraSession
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.helpers import device_registry as dr

from .const import DEFAULT_PORT, DISPLAY_MODEL, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class LinknLinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LinknLink."""

    VERSION = 1

    async def _async_connect_host(self, host: str) -> UltraSession:
        """Discover and authenticate a device at a host."""
        client = UltraClient(default_port=DEFAULT_PORT)
        device = await client.discover_host(host)
        return await client.connect(device)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle setup initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            self._async_abort_entries_match({CONF_HOST: host})
            try:
                session = await self._async_connect_host(host)
            except UltraError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception while connecting to LinknLink")
                errors["base"] = "unknown"
            else:
                mac = dr.format_mac(session.device.mac)
                port = session.device.port or DEFAULT_PORT
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: session.device.ip,
                        CONF_MAC: mac,
                        CONF_PORT: port,
                    }
                )
                return self.async_create_entry(
                    title=DISPLAY_MODEL,
                    data={
                        CONF_HOST: session.device.ip,
                        CONF_MAC: mac,
                        CONF_PORT: port,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the network address of an existing device."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if host != entry.data[CONF_HOST]:
                self._async_abort_entries_match({CONF_HOST: host})
            try:
                session = await self._async_connect_host(host)
            except UltraError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception while reconnecting to LinknLink")
                errors["base"] = "unknown"
            else:
                mac = dr.format_mac(session.device.mac)
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: session.device.ip,
                        CONF_MAC: mac,
                        CONF_PORT: session.device.port or DEFAULT_PORT,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or entry.data,
            ),
            description_placeholders={"device_name": entry.title},
            errors=errors,
        )
