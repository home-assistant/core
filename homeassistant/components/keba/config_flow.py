"""Config flow for the KEBA charging station integration."""

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from . import KebaHandler
from .const import (
    CONF_FS,
    CONF_FS_FALLBACK,
    CONF_FS_PERSIST,
    CONF_FS_TIMEOUT,
    CONF_RFID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Optional(CONF_RFID, default=""): TextSelector(),
        vol.Optional(CONF_FS, default=False): BooleanSelector(),
        vol.Optional(CONF_FS_TIMEOUT, default=30): NumberSelector(
            NumberSelectorConfig(min=10, max=600, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_FS_FALLBACK, default=6): NumberSelector(
            NumberSelectorConfig(min=6, max=63, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_FS_PERSIST, default=0): NumberSelector(
            NumberSelectorConfig(min=0, max=1, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


class KebaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KEBA charging station."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import configuration from configuration.yaml."""
        data = {
            CONF_HOST: import_data[CONF_HOST],
            CONF_RFID: import_data.get(CONF_RFID, ""),
            CONF_FS: import_data.get(CONF_FS, False),
            CONF_FS_TIMEOUT: import_data.get(CONF_FS_TIMEOUT, 30),
            CONF_FS_FALLBACK: import_data.get(CONF_FS_FALLBACK, 6),
            CONF_FS_PERSIST: import_data.get(CONF_FS_PERSIST, 0),
        }
        keba = KebaHandler(self.hass, data[CONF_HOST], data[CONF_RFID])
        try:
            connected = await keba.setup()
        except OSError:
            _LOGGER.exception(
                "Could not import KEBA config from configuration.yaml: "
                "failed to connect to %s",
                data[CONF_HOST],
            )
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception(
                "Could not import KEBA config from configuration.yaml: "
                "unexpected error while connecting to %s",
                data[CONF_HOST],
            )
            return self.async_abort(reason="unknown")

        if not connected:
            _LOGGER.error(
                "Could not import KEBA config from configuration.yaml: "
                "no charging station found at %s",
                data[CONF_HOST],
            )
            return self.async_abort(reason="cannot_connect")

        serial = str(keba.get_value("Serial"))
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=keba.device_name, data=data)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            keba = KebaHandler(self.hass, user_input[CONF_HOST], user_input[CONF_RFID])
            try:
                connected = await keba.setup()
            except OSError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to KEBA wallbox")
                errors["base"] = "unknown"
            else:
                if not connected:
                    errors["base"] = "cannot_connect"
                else:
                    serial = str(keba.get_value("Serial"))
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=keba.device_name,
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        entry: ConfigEntry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, entry.data
            ),
        )
