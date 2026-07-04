"""Config flow for the KEBA charging station integration."""

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
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
    DEFAULT_FS,
    DEFAULT_FS_FALLBACK,
    DEFAULT_FS_PERSIST,
    DEFAULT_FS_TIMEOUT,
    DEFAULT_RFID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Optional(CONF_RFID, default=DEFAULT_RFID): TextSelector(),
        vol.Optional(CONF_FS, default=DEFAULT_FS): BooleanSelector(),
        vol.Optional(CONF_FS_TIMEOUT, default=DEFAULT_FS_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=10, max=600, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_FS_FALLBACK, default=DEFAULT_FS_FALLBACK): NumberSelector(
            NumberSelectorConfig(min=6, max=63, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_FS_PERSIST, default=DEFAULT_FS_PERSIST): NumberSelector(
            NumberSelectorConfig(min=0, max=1, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


class KebaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KEBA charging station."""

    VERSION = 1

    async def _async_try_connect(
        self, host: str, rfid: str
    ) -> tuple[KebaHandler | None, dict[str, str]]:
        """Connect to the charging station and return the handler or form errors."""
        keba = KebaHandler(self.hass, host, rfid)
        try:
            connected = await keba.setup()
        except OSError:
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error connecting to KEBA wallbox")
            return None, {"base": "unknown"}
        if not connected:
            return None, {"base": "cannot_connect"}
        return keba, {}

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import configuration from configuration.yaml."""
        keba, errors = await self._async_try_connect(
            import_data[CONF_HOST], import_data[CONF_RFID]
        )
        if keba is None:
            _LOGGER.error(
                "Could not import KEBA config from configuration.yaml for %s: %s",
                import_data[CONF_HOST],
                errors["base"],
            )
            return self.async_abort(reason=errors["base"])

        await self.async_set_unique_id(str(keba.get_value("Serial")))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=keba.device_name, data=import_data)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            keba, errors = await self._async_try_connect(
                user_input[CONF_HOST], user_input[CONF_RFID]
            )
            if keba is not None:
                await self.async_set_unique_id(str(keba.get_value("Serial")))
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
