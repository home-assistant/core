from re import match as matches

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (CONF_FORCE_UPDATE, CONF_MAC,
                                 CONF_MONITORED_CONDITIONS, CONF_NAME,
                                 DEVICE_CLASS_BATTERY, DEVICE_CLASS_HUMIDITY,
                                 DEVICE_CLASS_TEMPERATURE)
from homeassistant.helpers import config_validation as cv

from . import (CONF_ADAPTER, CONF_CACHE, CONF_MEDIAN, CONF_RETRIES,
               CONF_TIMEOUT, DEFAULT_ADAPTER, DEFAULT_FORCE_UPDATE,
               DEFAULT_MEDIAN, DEFAULT_NAME, DEFAULT_RETRIES, DEFAULT_TIMEOUT,
               DEFAULT_UPDATE_INTERVAL, DOMAIN)


@config_entries.HANDLERS.register(DOMAIN)
class LYWSDCGQConfigFlow(config_entries.ConfigFlow):

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input={}):
        if user_input:
            return await self.create_entry_if_valid(user_input)

        return self.show_form()

    def show_form(self, user_input={}, errors={}):
        mac = user_input.get(CONF_MAC)
        median = user_input.get(CONF_MEDIAN, DEFAULT_MEDIAN)
        monitored_conditions = user_input.get(CONF_MONITORED_CONDITIONS)
        force_update = user_input.get(CONF_FORCE_UPDATE, DEFAULT_FORCE_UPDATE)
        timeout = user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        retries = user_input.get(CONF_RETRIES, DEFAULT_RETRIES)
        cache = user_input.get(CONF_CACHE, DEFAULT_UPDATE_INTERVAL)
        adapter = user_input.get(CONF_ADAPTER, DEFAULT_ADAPTER)
        SCHEMA = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_MAC, default=mac): str,
                vol.Required(
                    CONF_MONITORED_CONDITIONS, default=monitored_conditions
                ): cv.multi_select(
                    {
                        DEVICE_CLASS_TEMPERATURE: DEVICE_CLASS_TEMPERATURE,
                        DEVICE_CLASS_HUMIDITY: DEVICE_CLASS_HUMIDITY,
                        DEVICE_CLASS_BATTERY: DEVICE_CLASS_BATTERY,
                    }
                ),
                vol.Optional(CONF_MEDIAN, default=median): cv.positive_int,
                vol.Optional(CONF_FORCE_UPDATE, default=force_update): bool,
                vol.Optional(CONF_TIMEOUT, default=timeout): cv.positive_int,
                vol.Optional(CONF_RETRIES, default=retries): cv.positive_int,
                vol.Optional(CONF_CACHE, default=cache): cv.positive_int,
                vol.Optional(CONF_ADAPTER, default=adapter): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def create_entry_if_valid(self, user_input):
        mac = user_input.get(CONF_MAC)
        identifier = f"{DOMAIN}[{mac.lower()}]"
        if identifier in self._async_current_ids():
            return self.async_abort(reason="already_configured")

        mac_pattern = "^" + "[\:\-]".join(["([0-9a-f]{2})"] * 6) + "$"
        if not matches(mac_pattern, mac.lower()):
            return self.show_form(user_input=user_input, errors={"base": "wrong_mac"})

        if not user_input.get(CONF_MONITORED_CONDITIONS):
            return self.show_form(
                user_input=user_input, errors={"base": "nothing_checked"}
            )

        await self.async_set_unique_id(identifier)
        return self.async_create_entry(title=mac, data=user_input)
