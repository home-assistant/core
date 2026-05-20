"""Config flow for the Powersensor integration."""

from ipaddress import ip_address as _parse_ip
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
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
    ROLE_UNKNOWN,
    ROLE_UPDATE_SIGNAL,
    ROLE_WATER,
)

_LOGGER = logging.getLogger(__name__)


def get_sensor_display_name(config_entry: ConfigEntry, mac: str) -> str:
    """Return a human-readable label for a sensor given its MAC address.

    Uses the display_name stored in entry data when available (populated
    during zeroconf discovery), falling back to a plain MAC string.  This
    avoids reaching into the translation cache at reconfigure time, where the
    cache may not yet be populated.
    """
    devices: dict[str, dict[str, str]] = config_entry.data.get(CFG_DEVICES, {})
    device_info = devices.get(mac, {})
    return device_info.get("display_name") or f"Powersensor Sensor ({mac})"


class PowersensorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Powersensor."""

    VERSION = 2
    MINOR_VERSION = 2

    # Class-level dict shared across all flow instances for this domain.
    # When multiple plugs are discovered simultaneously, each triggers its own
    # async_step_zeroconf call on a fresh flow instance.  The first instance
    # wins the in-progress race and waits at discovery_confirm; subsequent
    # instances abort via already_in_progress — but not before writing their
    # plug info here.  When the user confirms, the winning instance reads from
    # this shared dict so all discovered plugs are included in CFG_DEVICES.
    # The dict is cleared after a successful async_create_entry so it does not
    # bleed across unrelated setup sessions.
    _pending_plugs: dict[str, dict[str, str | int]] = {}

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._my_plug_mac: str | None = None

    def async_remove(self) -> None:
        """Clean up when this flow is aborted or dismissed without completing.

        Removes this instance's plug contribution from the shared class-level
        dict so that a future setup session starts clean.  Only removes the
        entry written by *this* instance — the winning flow that called
        async_create_entry already cleared the dict via _async_confirm_step,
        so this guard handles flows that lost the in-progress race or whose
        confirmation dialog was closed by the user without confirming.
        """
        if self._my_plug_mac is not None:
            PowersensorConfigFlow._pending_plugs.pop(self._my_plug_mac, None)
            self._my_plug_mac = None

    async def async_step_reconfigure(
        self, user_input: dict[str, str | None] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure step. The primary use case is adding missing roles to sensors."""
        entry = self._get_reconfigure_entry()
        if not hasattr(entry, "runtime_data"):
            return self.async_abort(reason="cannot_reconfigure")

        dispatcher = entry.runtime_data.dispatcher
        if dispatcher is None:
            return self.async_abort(reason="cannot_reconfigure")

        mac2name = {
            mac: get_sensor_display_name(entry, mac) for mac in dispatcher.sensors
        }

        if user_input is not None:
            name2mac = {name: mac for mac, name in mac2name.items()}

            # Fire role-update signals first so that handle_role_update in
            # sensor.py sees the *old* role in entry.data when it runs its
            # old_role != new_role guard.  handle_role_update itself writes
            # the new role into entry.data, so we must not pre-persist here.
            for name, role in user_input.items():
                mac = name2mac.get(name)
                if mac is None:
                    continue
                resolved_role = None if role == ROLE_UNKNOWN else role
                _LOGGER.debug("Applying %s to %s", resolved_role, mac)
                async_dispatcher_send(self.hass, ROLE_UPDATE_SIGNAL, mac, resolved_role)

            return self.async_abort(reason="roles_applied")

        sensor_roles = {}
        for sensor_mac in dispatcher.sensors:
            role = entry.data.get(CFG_ROLES, {}).get(sensor_mac, ROLE_UNKNOWN)
            sel = selector(
                {
                    "select": {
                        "options": [
                            ROLE_HOUSENET,
                            ROLE_SOLAR,
                            ROLE_WATER,
                            ROLE_APPLIANCE,
                            ROLE_UNKNOWN,
                        ],
                        "mode": "dropdown",
                        "translation_key": "sensor_role",
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

        docs_url = "https://dius.github.io/homeassistant-powersensor/data.html#virtual-household"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(sensor_roles),
            description_placeholders={
                "docs_url": docs_url,
            },
        )

    async def _async_prepare_setup(self) -> ConfigFlowResult | None:
        """Register a unique ID and guard against duplicate entries or parallel flows.

        Checks for any already-in-progress flow first so that simultaneous
        zeroconf discoveries (multiple plugs seen at once) don't each try to
        start their own config flow. The first one wins; the rest abort.

        Then calls async_set_unique_id and _abort_if_unique_id_configured() to
        guard against starting a flow when an entry already exists.
        Returns None in the normal (non-duplicate, non-in-progress) case.
        """
        if self._async_in_progress(include_uninitialized=True):
            return self.async_abort(reason="already_in_progress")
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        self.context.update({"title_placeholders": {"name": "Powersensor"}})
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if result := await self._async_prepare_setup():
            return result
        return await self.async_step_manual_confirm()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of a Powersensor plug (gateway).

        Every zeroconf announcement arrives on a fresh flow instance, so
        instance-level state is useless for accumulating multiple plugs.
        Instead, each instance writes into the class-level _pending_plugs dict
        *before* the in-progress check so that even flows which lose the race
        contribute their plug.  The winning flow reads _pending_plugs on
        confirm; the dict is cleared afterward so it does not bleed into a
        future setup session.
        """
        raw_host = discovery_info.host
        host = raw_host if isinstance(raw_host, str) else str(_parse_ip(raw_host))
        port = discovery_info.port or DEFAULT_PORT
        properties = discovery_info.properties or {}

        if "id" not in properties:
            return self.async_abort(reason="firmware_not_compatible")

        mac = properties["id"].strip()
        display_name = f"Powersensor Plug ({mac})"

        # Write into the shared class-level dict before any abort checks so
        # that even flows that lose the in-progress race contribute their plug.
        # Only write (and claim ownership for cleanup) when this MAC is not
        # already present: a re-announcement of the same plug should not
        # overwrite the existing entry, and we must not set _my_plug_mac in
        # that case or async_remove will incorrectly pop the entry when this
        # duplicate flow aborts.
        if mac not in PowersensorConfigFlow._pending_plugs:
            PowersensorConfigFlow._pending_plugs[mac] = {
                "host": host,
                "port": port,
                "display_name": display_name,
                "mac": mac,
                "name": discovery_info.name,
            }
            self._my_plug_mac = mac

        if result := await self._async_prepare_setup():
            return result

        return await self.async_step_discovery_confirm()

    async def _async_confirm_step(
        self, step_id: str, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Shared confirmation step used by both discovery and manual flows."""
        if user_input is not None:
            plugs = dict(PowersensorConfigFlow._pending_plugs)
            _LOGGER.debug("Creating entry with discovered plugs: %s", plugs)
            PowersensorConfigFlow._pending_plugs.clear()
            return self.async_create_entry(
                title="Powersensor",
                data={
                    CFG_DEVICES: plugs,
                    CFG_ROLES: {},
                },
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
