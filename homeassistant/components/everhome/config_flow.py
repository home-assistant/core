"""Config flow for the everHome integration."""

from collections.abc import Mapping
from typing import Any, Final, override

from ecotracker import EcoTracker
import probatio

from homeassistant.config_entries import (
    SOURCE_ZEROCONF,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_FAST_POLLING, DOMAIN
from .coordinator import EcoTrackerConfigEntry

CONFIG_SCHEMA: Final = probatio.Schema({probatio.Required(CONF_HOST): str})
FAST_POLLING_SCHEMA: Final = probatio.Schema(
    {probatio.Optional(CONF_FAST_POLLING, default=False): bool}
)
USER_SCHEMA: Final = CONFIG_SCHEMA.extend(FAST_POLLING_SCHEMA.schema)
FAST_POLLING_MENU_OPTIONS: Final = ["fast_polling_enable", "fast_polling_cancel"]


class EcoTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EcoTracker."""

    VERSION = 1

    _host: str
    _serial: str

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: EcoTrackerConfigEntry,
    ) -> EcoTrackerOptionsFlow:
        """Create the options flow."""
        return EcoTrackerOptionsFlow()

    async def _async_get_serial(self, host: str) -> str | None:
        """Connect to the device and return its serial, or None if unreachable."""
        client = EcoTracker(host, port=80, session=async_get_clientsession(self.hass))
        if not await client.async_update():
            return None
        return client.get_data().serial

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            if (serial := await self._async_get_serial(host)) is None:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(serial, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                self._host = host
                self._serial = serial
                return await self._async_finish(user_input[CONF_FAST_POLLING])
        return self._async_show_user_form(errors=errors)

    @callback
    def _async_show_user_form(
        self,
        errors: dict[str, str] | None = None,
        suggested_values: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the user form."""
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.host
        if not (serial := discovery_info.properties.get("serial")):
            return self.async_abort(reason="no_serial")
        self._serial = serial
        await self.async_set_unique_id(self._serial)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        if await self._async_get_serial(self._host) is None:
            return self.async_abort(reason="cannot_connect")

        self.context["title_placeholders"] = {"name": f"EcoTracker {self._serial}"}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return await self._async_finish(user_input[CONF_FAST_POLLING])

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=FAST_POLLING_SCHEMA,
            description_placeholders={
                "name": "EcoTracker",
                "serial": self._serial,
                "host": self._host,
            },
        )

    async def _async_finish(self, fast_polling: bool) -> ConfigFlowResult:
        """Create the entry, asking for confirmation first if fast polling is on."""
        if fast_polling:
            return await self.async_step_fast_polling()
        return self._async_create_ecotracker_entry(fast_polling=False)

    async def async_step_fast_polling(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm fast polling."""
        return self.async_show_menu(
            step_id="fast_polling", menu_options=FAST_POLLING_MENU_OPTIONS
        )

    async def async_step_fast_polling_enable(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry with fast polling enabled."""
        return self._async_create_ecotracker_entry(fast_polling=True)

    async def async_step_fast_polling_cancel(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Return to the setup form with fast polling turned off."""
        if self.source == SOURCE_ZEROCONF:
            return await self.async_step_zeroconf_confirm()
        return self._async_show_user_form(suggested_values={CONF_HOST: self._host})

    @callback
    def _async_create_ecotracker_entry(self, fast_polling: bool) -> ConfigFlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title=f"EcoTracker {self._serial}",
            data={CONF_HOST: self._host},
            options={CONF_FAST_POLLING: fast_polling},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initiated by the user."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            if (serial := await self._async_get_serial(host)) is None:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )


class EcoTrackerOptionsFlow(OptionsFlowWithReload):
    """Handle EcoTracker options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the fast polling option."""
        if user_input is not None:
            fast_polling = user_input[CONF_FAST_POLLING]
            if fast_polling and not self.config_entry.options.get(
                CONF_FAST_POLLING, False
            ):
                return await self.async_step_fast_polling()
            return self.async_create_entry(data={CONF_FAST_POLLING: fast_polling})

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                FAST_POLLING_SCHEMA, self.config_entry.options
            ),
        )

    async def async_step_fast_polling(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm fast polling."""
        return self.async_show_menu(
            step_id="fast_polling", menu_options=FAST_POLLING_MENU_OPTIONS
        )

    async def async_step_fast_polling_enable(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enable fast polling."""
        return self.async_create_entry(data={CONF_FAST_POLLING: True})

    async def async_step_fast_polling_cancel(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Return to the options form without enabling fast polling."""
        return await self.async_step_init()
