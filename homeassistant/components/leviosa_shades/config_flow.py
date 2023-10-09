"""Config flow for Leviosa shades Zone."""
import logging

from leviosapy import discover_leviosa_zones, validate_zone
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BLIND_GROUPS,
    DEVICE_FW_V,
    DEVICE_MAC,
    DOMAIN,
    GROUP1_NAME,
    GROUP2_NAME,
    GROUP3_NAME,
    GROUP4_NAME,
    GROUP5_NAME,
    GROUP6_NAME,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(GROUP1_NAME): str,
        vol.Optional(GROUP2_NAME): str,
        vol.Optional(GROUP3_NAME): str,
        vol.Optional(GROUP4_NAME): str,
        vol.Optional(GROUP5_NAME): str,
        vol.Optional(GROUP6_NAME): str,
    }
)


@config_entries.HANDLERS.register(DOMAIN)
class LeviosaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Manages the interaction with user when a Leviosa Zone needs to be setup."""

    # The schema version below will be used by Home Assistant to determine
    # if a call to the migrate method is needed; this is not implemented
    # as of March 2021
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    GROUPS = [
        GROUP1_NAME,
        GROUP2_NAME,
        GROUP3_NAME,
        GROUP4_NAME,
        GROUP5_NAME,
        GROUP6_NAME,
    ]

    def __init__(self):
        """Initialize the Motion Blinds flow."""

        self._host = None
        self._host_uid = None
        self._devices = {}

    async def async_step_user(self, user_input=None):
        """Perform discovery and present an input screen for each Zone discovered."""

        _LOGGER.debug("Looking for Leviosa Zone HUBs")
        self._devices = await discover_leviosa_zones()
        _LOGGER.debug("Found %d Zones advertising on the network ", len(self._devices))
        devs_to_be_removed = []
        for dev_key in self._devices:
            if self._host_already_configured(self._devices[dev_key]):
                devs_to_be_removed.append(dev_key)
        for dev in devs_to_be_removed:
            self._devices.pop(dev)
        _LOGGER.info("There are %d Zones can be included in Hass", len(self._devices))
        Zones = list(self._devices.keys())
        if len(Zones) == 1:
            self._host = self._devices[Zones[0]]
            self._host_uid = Zones[0]
            return await self.async_step_connect()
        if len(Zones) > 1:
            return await self.async_step_select()

        return self.async_abort(reason="no_new_devs")

    async def async_step_select(self, user_input=None):
        """Handle multiple motion gateways found."""
        if user_input is not None:
            self._host = user_input["select_ip"]
            vals = list(self._devices.values())
            idx_of_ip = vals.index(self._host)
            keys = list(self._devices.keys())
            self._host_uid = keys[idx_of_ip]
            return await self.async_step_connect()

        select_schema = vol.Schema(
            {vol.Required("select_ip"): vol.In(self._devices.values())}
        )

        return self.async_show_form(step_id="select", data_schema=select_schema)

    async def async_step_connect(self, user_input=None):
        """Allow user to enter details for a Leviosa Zone."""
        errors = {}
        if user_input is not None:
            _LOGGER.debug(
                "Config User step - validate and save [%s] @%s",
                self._host_uid,
                self._host,
            )
            for i in user_input:
                _LOGGER.debug("UI %s -> %s", i, user_input[i])

            fw_ver = await validate_zone(async_get_clientsession(self.hass), self._host)
            if fw_ver == "invalid":
                errors["base"] = "cannot_connect"
            elif fw_ver is None:
                errors["base"] = "unknown"
            else:
                _LOGGER.debug("Saving Integration data")
                await self.async_set_unique_id(self._host_uid)
                bgs = []
                bgs.append("All " + user_input[CONF_NAME])
                for group in self.GROUPS:  # We'll create a list of valid groups
                    if user_input.get(group, "") != "":
                        bgs.append(user_input[group])
                    else:
                        break
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_HOST: self._host,
                        DEVICE_FW_V: fw_ver,
                        DEVICE_MAC: self._host_uid[-12:],
                        BLIND_GROUPS: bgs,
                    },
                )

        _LOGGER.debug("Config User step - display UI for %s", self._host)
        return self.async_show_form(
            step_id="connect",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={"ip_add": self._host},
        )

    def _host_already_configured(self, host):
        """See if we already have a hub with the host address configured."""
        _LOGGER.debug("Checking if HOST was already configured")
        existing_hosts = {
            entry.data.get(CONF_HOST)
            for entry in self._async_current_entries()
            if CONF_HOST in entry.data
        }
        return host in existing_hosts
