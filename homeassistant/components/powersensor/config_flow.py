"""Config flow for the integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.selector import selector
from homeassistant.helpers.service_info import zeroconf

from .const import (
    CFG_DEVICES,
    CFG_ROLES,
    DEFAULT_PORT,
    DOMAIN,
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_UPDATE_SIGNAL,
    ROLE_WATER,
    RT_DISPATCHER,
    SENSOR_NAME_FORMAT,
)
from ..websocket_api.util import describe_request

_LOGGER = logging.getLogger(__name__)


class PowersensorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure step. The primary use case is adding missing roles to sensors."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None or not hasattr(entry, "runtime_data"):
            return self.async_abort(
                reason="Cannot reconfigure. Initial configuration incomplete or broken."
            )

        dispatcher = entry.runtime_data[RT_DISPATCHER]
        if dispatcher is None:
            return self.async_abort(
                reason="Cannot reconfigure. Initial configuration incomplete or broken."
            )

        mac2name = {mac: SENSOR_NAME_FORMAT % mac for mac in dispatcher.sensors}

        unknown = "<unknown>"
        if user_input is not None:
            name2mac = {name: mac for mac, name in mac2name.items()}
            for name, role in user_input.items():
                mac = name2mac.get(name)
                if role == unknown:
                    role = None
                _LOGGER.debug("Applying %s to %s", role, mac)
                async_dispatcher_send(self.hass, ROLE_UPDATE_SIGNAL, mac, role)
            return self.async_abort(reason="Roles successfully applied!")

        sensor_roles = {}
        description_placeholders = {}
        for sensor_mac in dispatcher.sensors:
            role = entry.data.get(CFG_ROLES, {}).get(sensor_mac, unknown)
            sel = selector(
                {
                    "select": {
                        "options": [
                            # Note: these strings are NOT subject to translation
                            ROLE_HOUSENET,
                            ROLE_SOLAR,
                            ROLE_WATER,
                            ROLE_APPLIANCE,
                            unknown,
                        ],
                        "mode": "dropdown",
                    }
                }
            )
            sensor_name = mac2name[sensor_mac]
            sensor_roles[
                vol.Optional(
                    sensor_name,
                    description={"suggested_value": role, "name": sensor_name},
                )
            ] = sel
            description_placeholders[sensor_name] = sensor_name

        description_placeholders["device_count"] = str(len(sensor_roles))
        description_placeholders["docs_url"] = (
            "https://dius.github.io/homeassistant-powersensor/data.html#virtual-household"
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(sensor_roles),
            description_placeholders={
                "device_count": str(len(sensor_roles)),
                "docs_url": "https://dius.github.io/homeassistant-powersensor/data.html#virtual-household",
            },
        )

    async def _common_setup(self):
        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}

        discovered_plugs_key = "discovered_plugs"
        if discovered_plugs_key not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][discovered_plugs_key] = {}

        # register a unique id for the single power sensor entry
        await self.async_set_unique_id(DOMAIN)

        # abort now if configuration is on going in another thread (i.e. this thread isn't the first)
        if self._async_current_entries() or self._async_in_progress():
            _LOGGER.warning("Aborting - found existing entry!")
            return self.async_abort(reason="already_configured")

        display_name = "⚡ Powersensor 🔌\n"
        self.context.update({"title_placeholders": {"name": display_name}})
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        await self._common_setup()
        return await self.async_step_manual_confirm()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        await self._common_setup()
        discovered_plugs_key = "discovered_plugs"
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        properties = discovery_info.properties or {}
        mac = None
        if "id" in properties:
            mac = properties["id"].strip()
        else:
            return self.async_abort(reason="Plug firmware not compatible")

        display_name = f"🔌 Mac({mac})"
        plug_data = {
            "host": host,
            "port": port,
            "display_name": display_name,
            "mac": mac,
            "name": discovery_info.name,
        }

        if mac in self.hass.data[DOMAIN][discovered_plugs_key]:
            _LOGGER.debug("Mac found existing in data!")
        else:
            self.hass.data[DOMAIN][discovered_plugs_key][mac] = plug_data

        return await self.async_step_discovery_confirm()

    async def async_step_confirm(
        self, step_id: str, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        "Confirm user wants to add the powersensor integration with the plugs stored in hass.data['powersensor']."
        if user_input is not None:
            _LOGGER.debug(self.hass.data[DOMAIN]["discovered_plugs"])
            return self.async_create_entry(
                title="Powersensor",
                data={
                    CFG_DEVICES: self.hass.data[DOMAIN]["discovered_plugs"],
                    CFG_ROLES: {},
                },
            )
        return self.async_show_form(step_id=step_id)

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        "Confirm user wants to add the powersensor integration with the plugs discovered."
        return await self.async_step_confirm(
            step_id="discovery_confirm", user_input=user_input
        )

    async def async_step_manual_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        "Confirm user wants to add the powersensor integration with manual configuration (typically no plugs available)."
        return await self.async_step_confirm(
            step_id="manual_confirm", user_input=user_input
        )
