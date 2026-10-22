"""Config flow for LinknLink."""

from typing import Any, override

from aiolinknlink import UltraClient, UltraError, UltraSession
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr

from .const import DEFAULT_PORT, DISPLAY_MODEL, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
    }
)


class LinknLinkConfigFlow(ConfigFlow, domain=DOMAIN):
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
            try:
                session = await self._async_connect_host(host)
            except OSError, TimeoutError, UltraError, ValueError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception while connecting to LinknLink")
                errors["base"] = "unknown"
            else:
                mac = dr.format_mac(session.device.mac)
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: session.device.ip}
                )
                return self.async_create_entry(
                    title=DISPLAY_MODEL,
                    data={CONF_HOST: session.device.ip},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
