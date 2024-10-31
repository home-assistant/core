"""Config flow for Risco integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pyrisco import CannotConnectError, RiscoCloud, RiscoLocal, UnauthorizedError
import voluptuous as vol

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_DISARM_REQUIRED,
    CONF_COMMUNICATION_DELAY,
    CONF_CONCURRENCY,
    CONF_HA_STATES_TO_RISCO,
    CONF_RISCO_STATES_TO_HA,
    DEFAULT_ADVANCED_OPTIONS,
    DEFAULT_OPTIONS,
    DOMAIN,
    MAX_COMMUNICATION_DELAY,
    RISCO_STATES,
    TYPE_LOCAL,
)

_LOGGER = logging.getLogger(__name__)


CLOUD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_PIN): str,
    }
)
LOCAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=1000): int,
        vol.Required(CONF_PIN): str,
    }
)
HA_STATES = [
    AlarmControlPanelState.ARMED_AWAY.value,
    AlarmControlPanelState.ARMED_HOME.value,
    AlarmControlPanelState.ARMED_NIGHT.value,
    AlarmControlPanelState.ARMED_CUSTOM_BYPASS.value,
]


async def validate_cloud_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect to Risco Cloud.

    Data has the keys from CLOUD_SCHEMA with values provided by the user.
    """
    risco = RiscoCloud(data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PIN])

    try:
        await risco.login(async_get_clientsession(hass))
    finally:
        await risco.close()

    return {"title": risco.site_name}


async def validate_local_input(
    hass: HomeAssistant, data: Mapping[str, str]
) -> dict[str, Any]:
    """Validate the user input allows us to connect to a local panel.

    Data has the keys from LOCAL_SCHEMA with values provided by the user.
    """
    comm_delay = 0
    while True:
        risco = RiscoLocal(
            data[CONF_HOST],
            data[CONF_PORT],
            data[CONF_PIN],
            communication_delay=comm_delay,
        )
        try:
            await risco.connect()
        except CannotConnectError:
            if comm_delay >= MAX_COMMUNICATION_DELAY:
                raise
            comm_delay += 1
        else:
            break

    site_id = risco.id
    await risco.disconnect()
    return {"title": site_id, "comm_delay": comm_delay}


class RiscoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Risco."""

    VERSION = 1

    def __init__(self) -> None:
        """Init the config flow."""
        self._reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RiscoOptionsFlowHandler:
        """Define the config flow to handle options."""
        return RiscoOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["cloud", "local"],
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a cloud based alarm."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not self._reauth_entry:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()

            try:
                info = await validate_cloud_input(self.hass, user_input)
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except UnauthorizedError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not self._reauth_entry:
                    return self.async_create_entry(title=info["title"], data=user_input)
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data=user_input,
                    unique_id=user_input[CONF_USERNAME],
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="cloud", data_schema=CLOUD_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._reauth_entry = await self.async_set_unique_id(entry_data[CONF_USERNAME])
        return await self.async_step_cloud()

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a local based alarm."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_local_input(self.hass, user_input)
            except CannotConnectError as ex:
                _LOGGER.debug("Cannot connect", exc_info=ex)
                errors["base"] = "cannot_connect"
            except UnauthorizedError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["title"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        **user_input,
                        CONF_TYPE: TYPE_LOCAL,
                        CONF_COMMUNICATION_DELAY: info["comm_delay"],
                    },
                )

        return self.async_show_form(
            step_id="local", data_schema=LOCAL_SCHEMA, errors=errors
        )


class RiscoOptionsFlowHandler(OptionsFlow):
    """Handle a Risco options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry
        self._data = {**DEFAULT_OPTIONS, **config_entry.options}

    def _options_schema(self) -> vol.Schema:
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CODE_ARM_REQUIRED, default=self._data[CONF_CODE_ARM_REQUIRED]
                ): bool,
                vol.Required(
                    CONF_CODE_DISARM_REQUIRED,
                    default=self._data[CONF_CODE_DISARM_REQUIRED],
                ): bool,
            }
        )
        if self.show_advanced_options:
            self._data = {**DEFAULT_ADVANCED_OPTIONS, **self._data}
            schema = schema.extend(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=self._data[CONF_SCAN_INTERVAL]
                    ): int,
                    vol.Required(
                        CONF_CONCURRENCY, default=self._data[CONF_CONCURRENCY]
                    ): int,
                }
            )
        return schema

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            self._data = {**self._data, **user_input}
            return await self.async_step_risco_to_ha()

        return self.async_show_form(step_id="init", data_schema=self._options_schema())

    async def async_step_risco_to_ha(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Map Risco states to HA states."""
        if user_input is not None:
            self._data[CONF_RISCO_STATES_TO_HA] = user_input
            return await self.async_step_ha_to_risco()

        risco_to_ha = self._data[CONF_RISCO_STATES_TO_HA]
        options = vol.Schema(
            {
                vol.Required(risco_state, default=risco_to_ha[risco_state]): vol.In(
                    HA_STATES
                )
                for risco_state in RISCO_STATES
            }
        )

        return self.async_show_form(step_id="risco_to_ha", data_schema=options)

    async def async_step_ha_to_risco(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Map HA states to Risco states."""
        if user_input is not None:
            self._data[CONF_HA_STATES_TO_RISCO] = user_input
            return self.async_create_entry(title="", data=self._data)

        options = {}
        risco_to_ha = self._data[CONF_RISCO_STATES_TO_HA]
        # we iterate over HA_STATES, instead of set(self._risco_to_ha.values())
        # to ensure a consistent order
        for ha_state in HA_STATES:
            if ha_state not in risco_to_ha.values():
                continue

            values = [
                risco_state
                for risco_state in RISCO_STATES
                if risco_to_ha[risco_state] == ha_state
            ]
            current = self._data[CONF_HA_STATES_TO_RISCO].get(ha_state)
            if current not in values:
                current = values[0]
            options[vol.Required(ha_state, default=current)] = vol.In(values)

        return self.async_show_form(
            step_id="ha_to_risco", data_schema=vol.Schema(options)
        )
