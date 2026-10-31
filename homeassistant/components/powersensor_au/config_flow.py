"""Config flow for the Powersensor integration."""

import logging
from typing import Any, override

import probatio

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState, ConfigFlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info import zeroconf

from .const import (
    CFG_ROLES,
    DOMAIN,
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_UNKNOWN,
    ROLE_WATER,
)
from .models import PowersensorConfigEntry

_LOGGER = logging.getLogger(__name__)

CONF_ROLE = "role"
DOCS_URL = "https://www.home-assistant.io/integrations/powersensor_au/#reconfiguration"

ROLE_OPTIONS = [ROLE_HOUSENET, ROLE_SOLAR, ROLE_WATER, ROLE_APPLIANCE, ROLE_UNKNOWN]

SENSOR_ROLE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ROLE): SelectSelector(
            SelectSelectorConfig(
                options=ROLE_OPTIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="sensor_role",
            )
        )
    }
)


class PowersensorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Powersensor."""

    VERSION = 1
    MINOR_VERSION = 1

    _pending_macs: list[str]
    _chosen_roles: dict[str, str | None]

    async def async_step_reconfigure(
        self, user_input: dict[str, str | None] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure step. The primary use case is adding roles to sensors.

        This is a workaround rather than part of normal setup.  Roles come from
        the hardware, and a sensor that reports one overrides what is set here.
        It exists for sensors that have forgotten their own role — a rev 6
        sensor whose battery ran flat, say — and never report one again.
        """
        entry: PowersensorConfigEntry = self._get_reconfigure_entry()

        # The sensor list only exists in runtime discovery state.
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        self._pending_macs = list(entry.runtime_data.dispatcher.sensors)
        if not self._pending_macs:
            return self.async_abort(reason="no_sensors_found")

        self._chosen_roles = {}
        return await self.async_step_sensor_role()

    async def async_step_sensor_role(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Ask for the role of each discovered sensor, one sensor per step."""
        entry = self._get_reconfigure_entry()
        # The integration keeps saving the roles sensors report while this flow
        # is open, so read the saved roles as they are now rather than when the
        # flow started, and change only the ones the user was asked about.
        if user_input is not None:
            mac = self._pending_macs.pop(0)
            role = user_input[CONF_ROLE]
            self._chosen_roles[mac] = None if role == ROLE_UNKNOWN else role
            if not self._pending_macs:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CFG_ROLES: {**entry.data[CFG_ROLES], **self._chosen_roles}
                    },
                )

        mac = self._pending_macs[0]
        # A role newer firmware reported may not be one of the selector options.
        suggested = entry.data[CFG_ROLES].get(mac)
        if suggested not in ROLE_OPTIONS:
            suggested = ROLE_UNKNOWN
        return self.async_show_form(
            step_id="sensor_role",
            data_schema=self.add_suggested_values_to_schema(
                SENSOR_ROLE_SCHEMA, {CONF_ROLE: suggested}
            ),
            description_placeholders={
                "sensor": self._sensor_name(entry.entry_id, mac),
                "docs_url": DOCS_URL,
            },
            last_step=len(self._pending_macs) == 1,
        )

    def _sensor_name(self, entry_id: str, mac: str) -> str:
        """Return the name the user sees for this sensor in the device registry."""
        device = dr.async_get(self.hass).async_get_device_by_identifier(
            (DOMAIN, mac), entry_id
        )
        if device is None:
            return mac
        return device.name_by_user or device.name or mac

    async def _async_prepare_setup(self) -> None:
        """Register the unique ID, aborting if another flow is already in progress."""
        # Not about existing entries, which single_config_entry already rules
        # out: this stops every discovered plug from opening its own flow, and
        # lets the user ignore a discovery.
        await self.async_set_unique_id(DOMAIN)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        await self._async_prepare_setup()
        return await self.async_step_manual_confirm()

    @override
    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of a Powersensor plug.

        Zeroconf is used only to trigger config entry creation when a
        Powersensor device is first seen on the network.  All ongoing
        plug discovery and connection management is handled by the
        powersensor_local library.
        """
        if "id" not in discovery_info.properties:
            # Aborting the first step of a discovery flow shows nothing to the
            # user, so log why the plug was skipped.
            _LOGGER.debug(
                "Ignoring %s: no id in its zeroconf properties, firmware not compatible",
                discovery_info.name,
            )
            return self.async_abort(reason="firmware_not_compatible")

        await self._async_prepare_setup()

        return await self.async_step_discovery_confirm()

    async def _async_confirm_step(
        self, step_id: str, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Shared confirmation step used by both discovery and manual flows."""
        if user_input is not None:
            return self.async_create_entry(
                title="Powersensor",
                data={CFG_ROLES: {}},
            )
        return self.async_show_form(step_id=step_id)

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the user wants to add the discovered Powersensor integration."""
        return await self._async_confirm_step(
            step_id="discovery_confirm", user_input=user_input
        )

    async def async_step_manual_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the user wants to add the integration without discovered plugs."""
        return await self._async_confirm_step(
            step_id="manual_confirm", user_input=user_input
        )
