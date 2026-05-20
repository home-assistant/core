"""Config flow for Connectivity Monitor integration."""

from __future__ import annotations

from ipaddress import IPv4Address, ip_address
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .bluetooth import async_get_bluetooth_devices
from .const import (
    AD_DC_PORTS,
    CONF_ALERT_ACTION,
    CONF_ALERT_ACTION_DELAY,
    CONF_ALERT_ACTION_ENABLED,
    CONF_ALERT_DELAY,
    CONF_ALERT_GROUP,
    CONF_ALERTS_ENABLED,
    CONF_BLUETOOTH_ADDRESS,
    CONF_DNS_SERVER,
    CONF_ESPHOME_DEVICE_ID,
    CONF_INACTIVE_TIMEOUT,
    CONF_INTERVAL,
    CONF_MATTER_NODE_ID,
    CONF_PROTOCOL,
    CONF_TARGETS,
    CONF_ZHA_IEEE,
    DEFAULT_ALERT_ACTION_DELAY,
    DEFAULT_ALERT_DELAY,
    DEFAULT_ALERT_GROUP,
    DEFAULT_DNS_SERVER,
    DEFAULT_INACTIVE_TIMEOUT,
    DEFAULT_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_PROTOCOL,
    DOMAIN,
    PROTOCOL_AD_DC,
    PROTOCOL_BLUETOOTH,
    PROTOCOL_ESPHOME,
    PROTOCOL_ICMP,
    PROTOCOL_MATTER,
    PROTOCOL_TCP,
    PROTOCOL_UDP,
    PROTOCOL_ZHA,
)
from .esphome import async_get_esphome_devices
from .matter import async_get_matter_devices
from .network import NetworkProbe
from .zha import async_get_zha_devices

_LOGGER = logging.getLogger(__name__)

NETWORK_PROTOCOLS = {
    PROTOCOL_TCP,
    PROTOCOL_UDP,
    PROTOCOL_ICMP,
    PROTOCOL_AD_DC,
}


def is_valid_ip(ip: str) -> bool:
    """Check if string is valid IP address."""
    try:
        return isinstance(ip_address(ip), IPv4Address)
    except ValueError:
        return False


class ConnectivityMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Connectivity Monitor."""

    VERSION = 2

    # Unique IDs and titles for each typed entry
    ENTRY_UNIQUE_IDS = {
        "bluetooth": "connectivity_monitor_bluetooth",
        "esphome": "connectivity_monitor_esphome",
        "matter": "connectivity_monitor_matter",
        "network": "connectivity_monitor_network",
        "zha": "connectivity_monitor_zha",
    }
    ENTRY_TITLES = {
        "bluetooth": "Bluetooth Monitor",
        "esphome": "ESPHome Monitor",
        "matter": "Matter Monitor",
        "network": "Network Monitor",
        "zha": "ZigBee Monitor",
    }

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        # ZHA device selection state (reused across main and options flows)
        self._zha_selected_ieee: str | None = None
        self._zha_selected_name: str | None = None
        self._zha_selected_model: str | None = None
        self._zha_selected_manufacturer: str | None = None
        # Matter device selection state
        self._matter_selected_node_id: str | None = None
        self._matter_selected_name: str | None = None
        self._matter_selected_model: str | None = None
        self._matter_selected_manufacturer: str | None = None
        # ESPHome device selection state
        self._esphome_selected_device_id: str | None = None
        self._esphome_selected_name: str | None = None
        self._esphome_selected_model: str | None = None
        self._esphome_selected_manufacturer: str | None = None
        self._esphome_selected_identifier: str | None = None
        self._esphome_selected_mac: str | None = None
        # Bluetooth device selection state
        self._bluetooth_selected_address: str | None = None
        self._bluetooth_selected_name: str | None = None
        self._bluetooth_selected_model: str | None = None
        self._bluetooth_selected_manufacturer: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def _async_get_notify_groups(self):
        """Get list of notification groups from Home Assistant."""
        notify_services = self.hass.services.async_services().get("notify", {})
        return {name: name.replace("notify.", "") for name in notify_services}

    async def _async_get_alert_actions(self):
        """Get available automations and scripts that can be triggered as alert actions."""
        actions = {}
        for state in self.hass.states.async_all():
            entity_id = state.entity_id
            domain = entity_id.split(".")[0]
            if domain in ("automation", "script"):
                name = state.attributes.get("friendly_name") or entity_id
                actions[entity_id] = f"{name} ({entity_id})"
        return dict(sorted(actions.items(), key=lambda x: x[1].lower()))

    async def _async_validate_network_target(self) -> bool:
        """Check that the configured network target can be reached before setup."""
        protocol = self._data.get(CONF_PROTOCOL)
        host = self._data.get(CONF_HOST)
        if protocol not in NETWORK_PROTOCOLS or not host:
            return True

        probe = NetworkProbe(
            self.hass,
            self._data.get(CONF_DNS_SERVER, DEFAULT_DNS_SERVER),
        )

        if protocol == PROTOCOL_AD_DC:
            validation_targets = [
                {
                    CONF_HOST: host,
                    CONF_PROTOCOL: PROTOCOL_TCP,
                    CONF_PORT: port,
                }
                for port in AD_DC_PORTS
            ]
        else:
            validation_target = {
                CONF_HOST: host,
                CONF_PROTOCOL: protocol,
            }
            if protocol in (PROTOCOL_TCP, PROTOCOL_UDP):
                validation_target[CONF_PORT] = self._data[CONF_PORT]
            validation_targets = [validation_target]

        try:
            for validation_target in validation_targets:
                result = await probe.async_update_target(validation_target)
                if result.get("connected"):
                    return True
        except (KeyError, OSError, ValueError) as err:
            _LOGGER.debug("Network validation failed for %s: %s", host, err)

        return False

    async def async_step_import(self, data) -> ConfigFlowResult:
        """Handle import from automated migration — creates a typed entry directly."""
        entry_type = data.get("entry_type", "network")
        unique_id = self.ENTRY_UNIQUE_IDS.get(
            entry_type, f"connectivity_monitor_{entry_type}"
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self.ENTRY_TITLES.get(entry_type, "Connectivity Monitor"),
            data={
                CONF_TARGETS: data.get(CONF_TARGETS, []),
                CONF_INTERVAL: data.get(CONF_INTERVAL, DEFAULT_INTERVAL),
                CONF_DNS_SERVER: data.get(CONF_DNS_SERVER, DEFAULT_DNS_SERVER),
            },
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initiated by the user — choose device type."""
        # Copy shared settings (interval, DNS) from any existing entry but do NOT
        # pre-populate targets — each device type now lives in its own typed entry.
        entries = self._async_current_entries()
        if entries:
            entry = entries[0]
            self._data = {
                CONF_INTERVAL: entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL),
                CONF_DNS_SERVER: entry.data.get(CONF_DNS_SERVER, DEFAULT_DNS_SERVER),
                CONF_TARGETS: [],
            }

        if user_input is not None:
            if user_input["device_type"] == "zha":
                return await self.async_step_zha_device()
            if user_input["device_type"] == "matter":
                return await self.async_step_matter_device()
            if user_input["device_type"] == "esphome":
                return await self.async_step_esphome_device()
            if user_input["device_type"] == "bluetooth":
                return await self.async_step_bluetooth_device()
            return await self.async_step_network()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("device_type", default="network"): vol.In(
                        {
                            "bluetooth": "Bluetooth Device",
                            "esphome": "ESPHome Device",
                            "matter": "Matter Device",
                            "network": "Network Device (TCP / UDP / ICMP / AD)",
                            "zha": "ZigBee Device (ZHA)",
                        }
                    ),
                }
            ),
        )

    async def async_step_network(self, user_input=None) -> ConfigFlowResult:
        """Configure a network device to monitor."""
        errors = {}
        entries = self._async_current_entries()

        if user_input is not None:
            try:
                self._data.update(
                    {
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PROTOCOL: user_input[CONF_PROTOCOL],
                        "device_name": user_input.get("device_name", ""),
                        CONF_ALERTS_ENABLED: user_input.get(CONF_ALERTS_ENABLED, False),
                        CONF_ALERT_GROUP: (
                            user_input.get(CONF_ALERT_GROUP, "") or DEFAULT_ALERT_GROUP
                        )
                        if user_input.get(CONF_ALERTS_ENABLED)
                        else DEFAULT_ALERT_GROUP,
                        CONF_ALERT_DELAY: user_input.get(
                            CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY
                        ),
                        CONF_ALERT_ACTION_ENABLED: user_input.get(
                            CONF_ALERT_ACTION_ENABLED, False
                        ),
                        CONF_ALERT_ACTION: (user_input.get(CONF_ALERT_ACTION, "") or "")
                        if user_input.get(CONF_ALERT_ACTION_ENABLED)
                        else "",
                        CONF_ALERT_ACTION_DELAY: user_input.get(
                            CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
                        ),
                    }
                )

                protocol = self._data[CONF_PROTOCOL]
                if protocol in [PROTOCOL_TCP, PROTOCOL_UDP]:
                    return await self.async_step_port()
                if not entries:
                    return await self.async_step_dns()
            except Exception:
                _LOGGER.exception("Error in network step")
                errors["base"] = "unknown"
            else:
                if not await self._async_validate_network_target():
                    errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_finish()

        notify_groups = await self._async_get_notify_groups()
        alert_actions = await self._async_get_alert_actions()

        schema = {
            vol.Required(CONF_HOST): str,
            vol.Optional("device_name", description={"suggested_value": ""}): str,
            vol.Required(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.In(
                {
                    PROTOCOL_TCP: "TCP (Custom Port)",
                    PROTOCOL_UDP: "UDP (Custom Port)",
                    PROTOCOL_ICMP: "ICMP (Ping)",
                    PROTOCOL_AD_DC: "Active Directory DC",
                }
            ),
            vol.Optional(CONF_ALERTS_ENABLED, default=False): bool,
            vol.Required(CONF_ALERT_DELAY, default=DEFAULT_ALERT_DELAY): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
        }

        if notify_groups:
            notify_groups_dict = {k: f"notify.{v}" for k, v in notify_groups.items()}
            notify_groups_dict[""] = "No alert group"
            schema[vol.Optional(CONF_ALERT_GROUP, default="")] = vol.In(
                notify_groups_dict
            )

        schema[vol.Optional(CONF_ALERT_ACTION_ENABLED, default=False)] = bool
        schema[
            vol.Required(CONF_ALERT_ACTION_DELAY, default=DEFAULT_ALERT_ACTION_DELAY)
        ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=120))
        if alert_actions:
            actions_dict = {"": "No action"}
            actions_dict.update(alert_actions)
            schema[vol.Optional(CONF_ALERT_ACTION, default="")] = vol.In(actions_dict)

        return self.async_show_form(
            step_id="network",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_zha_device(self, user_input=None) -> ConfigFlowResult:
        """Select a ZHA device to add to monitoring (main config flow)."""
        entries = self._async_current_entries()
        zha_entry = next(
            (e for e in entries if e.unique_id == self.ENTRY_UNIQUE_IDS["zha"]), None
        )
        existing_ieees = {
            t.get(CONF_ZHA_IEEE)
            for t in (zha_entry.data.get(CONF_TARGETS, []) if zha_entry else [])
            if t.get(CONF_ZHA_IEEE)
        }

        zha_devices = await async_get_zha_devices(self.hass)
        if not zha_devices:
            return self.async_show_form(
                step_id="zha_device",
                errors={"base": "no_zha_devices"},
                data_schema=vol.Schema({}),
            )

        available = [d for d in zha_devices if d["ieee"] not in existing_ieees]
        if not available:
            return self.async_show_form(
                step_id="zha_device",
                errors={"base": "all_zha_devices_added"},
                data_schema=vol.Schema({}),
            )

        if user_input is not None:
            self._zha_selected_ieee = user_input[CONF_ZHA_IEEE]
            matched = next(
                (d for d in zha_devices if d["ieee"] == self._zha_selected_ieee), {}
            )
            self._zha_selected_name = matched.get("name") or self._zha_selected_ieee
            self._zha_selected_model = matched.get("model")
            self._zha_selected_manufacturer = matched.get("manufacturer")
            return await self.async_step_zha_configure()

        device_choices = {
            d["ieee"]: f"{d['name']} ({d['ieee']})"
            for d in sorted(available, key=lambda x: x["name"].lower())
        }
        return self.async_show_form(
            step_id="zha_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZHA_IEEE): vol.In(device_choices),
                }
            ),
        )

    async def async_step_zha_configure(self, user_input=None) -> ConfigFlowResult:
        """Set device name, inactivity timeout, and alert settings for the selected ZHA device."""
        entries = self._async_current_entries()

        if user_input is not None:
            device_name = (
                user_input.get("device_name") or ""
            ).strip() or self._zha_selected_name
            alerts_enabled = user_input.get(CONF_ALERTS_ENABLED, False)
            action_enabled = user_input.get(CONF_ALERT_ACTION_ENABLED, False)
            new_target = {
                CONF_PROTOCOL: PROTOCOL_ZHA,
                CONF_HOST: f"zha:{self._zha_selected_ieee}",
                CONF_ZHA_IEEE: self._zha_selected_ieee,
                "device_name": device_name,
                CONF_INACTIVE_TIMEOUT: user_input[CONF_INACTIVE_TIMEOUT],
                CONF_ALERT_GROUP: (
                    user_input.get(CONF_ALERT_GROUP, "") or DEFAULT_ALERT_GROUP
                )
                if alerts_enabled
                else DEFAULT_ALERT_GROUP,
                CONF_ALERT_DELAY: user_input.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY),
                CONF_ALERT_ACTION: (user_input.get(CONF_ALERT_ACTION, "") or "")
                if action_enabled
                else "",
                CONF_ALERT_ACTION_DELAY: user_input.get(
                    CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
                ),
            }
            if self._zha_selected_model:
                new_target["model"] = self._zha_selected_model
            if self._zha_selected_manufacturer:
                new_target["manufacturer"] = self._zha_selected_manufacturer

            targets = list(self._data.get(CONF_TARGETS, []))
            targets.append(new_target)
            self._data[CONF_TARGETS] = targets
            self._data[CONF_PROTOCOL] = PROTOCOL_ZHA  # signal finish() to skip port/DNS

            if not entries:
                # First-ever entry: still need DNS + interval
                return await self.async_step_dns()
            return await self.async_step_finish()

        notify_groups = await self._async_get_notify_groups()
        alert_actions = await self._async_get_alert_actions()
        schema = {
            vol.Optional("device_name", default=self._zha_selected_name or ""): str,
            vol.Required(
                CONF_INACTIVE_TIMEOUT, default=DEFAULT_INACTIVE_TIMEOUT
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
            vol.Optional(CONF_ALERTS_ENABLED, default=False): bool,
            vol.Required(CONF_ALERT_DELAY, default=DEFAULT_ALERT_DELAY): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
        }
        if notify_groups:
            notify_groups_dict = {k: f"notify.{v}" for k, v in notify_groups.items()}
            notify_groups_dict[""] = "No alert group"
            schema[vol.Optional(CONF_ALERT_GROUP, default="")] = vol.In(
                notify_groups_dict
            )
        schema[vol.Optional(CONF_ALERT_ACTION_ENABLED, default=False)] = bool
        schema[
            vol.Required(CONF_ALERT_ACTION_DELAY, default=DEFAULT_ALERT_ACTION_DELAY)
        ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=120))
        if alert_actions:
            actions_dict = {"": "No action"}
            actions_dict.update(alert_actions)
            schema[vol.Optional(CONF_ALERT_ACTION, default="")] = vol.In(actions_dict)

        return self.async_show_form(
            step_id="zha_configure",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "device_name": self._zha_selected_name or "",
                "ieee": self._zha_selected_ieee or "",
            },
        )

    async def async_step_matter_device(self, user_input=None) -> ConfigFlowResult:
        """Select a Matter device to add to monitoring (main config flow)."""
        entries = self._async_current_entries()
        matter_entry = next(
            (e for e in entries if e.unique_id == self.ENTRY_UNIQUE_IDS["matter"]), None
        )
        existing_node_ids = {
            t.get(CONF_MATTER_NODE_ID)
            for t in (matter_entry.data.get(CONF_TARGETS, []) if matter_entry else [])
            if t.get(CONF_MATTER_NODE_ID)
        }

        matter_devices = await async_get_matter_devices(self.hass)
        if not matter_devices:
            return self.async_show_form(
                step_id="matter_device",
                errors={"base": "no_matter_devices"},
                data_schema=vol.Schema({}),
            )

        available = [d for d in matter_devices if d["node_id"] not in existing_node_ids]
        if not available:
            return self.async_show_form(
                step_id="matter_device",
                errors={"base": "all_matter_devices_added"},
                data_schema=vol.Schema({}),
            )

        if user_input is not None:
            self._matter_selected_node_id = user_input[CONF_MATTER_NODE_ID]
            matched = next(
                (
                    d
                    for d in matter_devices
                    if d["node_id"] == self._matter_selected_node_id
                ),
                {},
            )
            self._matter_selected_name = (
                matched.get("name") or self._matter_selected_node_id
            )
            self._matter_selected_model = matched.get("model")
            self._matter_selected_manufacturer = matched.get("manufacturer")
            return await self.async_step_matter_configure()

        device_choices = {
            d["node_id"]: f"{d['name']} ({d['node_id']})"
            for d in sorted(available, key=lambda x: x["name"].lower())
        }
        return self.async_show_form(
            step_id="matter_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MATTER_NODE_ID): vol.In(device_choices),
                }
            ),
        )

    async def async_step_matter_configure(self, user_input=None) -> ConfigFlowResult:
        """Set device name, inactivity timeout, and alert settings for the selected Matter device."""
        entries = self._async_current_entries()

        if user_input is not None:
            device_name = (
                user_input.get("device_name") or ""
            ).strip() or self._matter_selected_name
            alerts_enabled = user_input.get(CONF_ALERTS_ENABLED, False)
            action_enabled = user_input.get(CONF_ALERT_ACTION_ENABLED, False)
            new_target = {
                CONF_PROTOCOL: PROTOCOL_MATTER,
                CONF_HOST: f"matter:{self._matter_selected_node_id}",
                CONF_MATTER_NODE_ID: self._matter_selected_node_id,
                "device_name": device_name,
                CONF_ALERT_GROUP: (
                    user_input.get(CONF_ALERT_GROUP, "") or DEFAULT_ALERT_GROUP
                )
                if alerts_enabled
                else DEFAULT_ALERT_GROUP,
                CONF_ALERT_DELAY: user_input.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY),
                CONF_ALERT_ACTION: (user_input.get(CONF_ALERT_ACTION, "") or "")
                if action_enabled
                else "",
                CONF_ALERT_ACTION_DELAY: user_input.get(
                    CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
                ),
            }
            if self._matter_selected_model:
                new_target["model"] = self._matter_selected_model
            if self._matter_selected_manufacturer:
                new_target["manufacturer"] = self._matter_selected_manufacturer

            targets = list(self._data.get(CONF_TARGETS, []))
            targets.append(new_target)
            self._data[CONF_TARGETS] = targets
            self._data[CONF_PROTOCOL] = PROTOCOL_MATTER

            if not entries:
                return await self.async_step_dns()
            return await self.async_step_finish()

        notify_groups = await self._async_get_notify_groups()
        alert_actions = await self._async_get_alert_actions()
        schema = {
            vol.Optional("device_name", default=self._matter_selected_name or ""): str,
            vol.Optional(CONF_ALERTS_ENABLED, default=False): bool,
            vol.Required(CONF_ALERT_DELAY, default=DEFAULT_ALERT_DELAY): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
        }
        if notify_groups:
            notify_groups_dict = {k: f"notify.{v}" for k, v in notify_groups.items()}
            notify_groups_dict[""] = "No alert group"
            schema[vol.Optional(CONF_ALERT_GROUP, default="")] = vol.In(
                notify_groups_dict
            )
        schema[vol.Optional(CONF_ALERT_ACTION_ENABLED, default=False)] = bool
        schema[
            vol.Required(CONF_ALERT_ACTION_DELAY, default=DEFAULT_ALERT_ACTION_DELAY)
        ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=120))
        if alert_actions:
            actions_dict = {"": "No action"}
            actions_dict.update(alert_actions)
            schema[vol.Optional(CONF_ALERT_ACTION, default="")] = vol.In(actions_dict)

        return self.async_show_form(
            step_id="matter_configure",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "device_name": self._matter_selected_name or "",
                "node_id": self._matter_selected_node_id or "",
            },
        )

    async def async_step_esphome_device(self, user_input=None) -> ConfigFlowResult:
        """Select an ESPHome device to add to monitoring (main config flow)."""
        entries = self._async_current_entries()
        esphome_entry = next(
            (e for e in entries if e.unique_id == self.ENTRY_UNIQUE_IDS["esphome"]),
            None,
        )
        existing_device_ids = {
            t.get(CONF_ESPHOME_DEVICE_ID)
            for t in (esphome_entry.data.get(CONF_TARGETS, []) if esphome_entry else [])
            if t.get(CONF_ESPHOME_DEVICE_ID)
        }

        esphome_devices = await async_get_esphome_devices(self.hass)
        if not esphome_devices:
            return self.async_show_form(
                step_id="esphome_device",
                errors={"base": "no_esphome_devices"},
                data_schema=vol.Schema({}),
            )

        available = [
            d for d in esphome_devices if d["device_id"] not in existing_device_ids
        ]
        if not available:
            return self.async_show_form(
                step_id="esphome_device",
                errors={"base": "all_esphome_devices_added"},
                data_schema=vol.Schema({}),
            )

        if user_input is not None:
            self._esphome_selected_device_id = user_input[CONF_ESPHOME_DEVICE_ID]
            matched = next(
                (
                    d
                    for d in esphome_devices
                    if d["device_id"] == self._esphome_selected_device_id
                ),
                {},
            )
            self._esphome_selected_name = (
                matched.get("name") or self._esphome_selected_device_id
            )
            self._esphome_selected_model = matched.get("model")
            self._esphome_selected_manufacturer = matched.get("manufacturer")
            self._esphome_selected_identifier = matched.get("esphome_identifier")
            self._esphome_selected_mac = matched.get("esphome_mac")
            return await self.async_step_esphome_configure()

        device_choices = {
            d["device_id"]: f"{d['name']} ({d['device_id']})"
            for d in sorted(available, key=lambda x: x["name"].lower())
        }
        return self.async_show_form(
            step_id="esphome_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ESPHOME_DEVICE_ID): vol.In(device_choices),
                }
            ),
        )

    async def async_step_esphome_configure(self, user_input=None) -> ConfigFlowResult:
        """Set device name and alert settings for the selected ESPHome device."""
        entries = self._async_current_entries()

        if user_input is not None:
            device_name = (
                user_input.get("device_name") or ""
            ).strip() or self._esphome_selected_name
            alerts_enabled = user_input.get(CONF_ALERTS_ENABLED, False)
            action_enabled = user_input.get(CONF_ALERT_ACTION_ENABLED, False)
            new_target = {
                CONF_PROTOCOL: PROTOCOL_ESPHOME,
                CONF_HOST: f"esphome:{self._esphome_selected_device_id}",
                CONF_ESPHOME_DEVICE_ID: self._esphome_selected_device_id,
                "esphome_identifier": self._esphome_selected_identifier,
                "esphome_mac": self._esphome_selected_mac,
                "device_name": device_name,
                CONF_ALERT_GROUP: (
                    user_input.get(CONF_ALERT_GROUP, "") or DEFAULT_ALERT_GROUP
                )
                if alerts_enabled
                else DEFAULT_ALERT_GROUP,
                CONF_ALERT_DELAY: user_input.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY),
                CONF_ALERT_ACTION: (user_input.get(CONF_ALERT_ACTION, "") or "")
                if action_enabled
                else "",
                CONF_ALERT_ACTION_DELAY: user_input.get(
                    CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
                ),
            }
            if self._esphome_selected_model:
                new_target["model"] = self._esphome_selected_model
            if self._esphome_selected_manufacturer:
                new_target["manufacturer"] = self._esphome_selected_manufacturer

            targets = list(self._data.get(CONF_TARGETS, []))
            targets.append(new_target)
            self._data[CONF_TARGETS] = targets
            self._data[CONF_PROTOCOL] = PROTOCOL_ESPHOME

            if not entries:
                return await self.async_step_dns()
            return await self.async_step_finish()

        notify_groups = await self._async_get_notify_groups()
        alert_actions = await self._async_get_alert_actions()
        schema = {
            vol.Optional("device_name", default=self._esphome_selected_name or ""): str,
            vol.Optional(CONF_ALERTS_ENABLED, default=False): bool,
            vol.Required(CONF_ALERT_DELAY, default=DEFAULT_ALERT_DELAY): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
        }
        if notify_groups:
            notify_groups_dict = {k: f"notify.{v}" for k, v in notify_groups.items()}
            notify_groups_dict[""] = "No alert group"
            schema[vol.Optional(CONF_ALERT_GROUP, default="")] = vol.In(
                notify_groups_dict
            )
        schema[vol.Optional(CONF_ALERT_ACTION_ENABLED, default=False)] = bool
        schema[
            vol.Required(CONF_ALERT_ACTION_DELAY, default=DEFAULT_ALERT_ACTION_DELAY)
        ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=120))
        if alert_actions:
            actions_dict = {"": "No action"}
            actions_dict.update(alert_actions)
            schema[vol.Optional(CONF_ALERT_ACTION, default="")] = vol.In(actions_dict)

        return self.async_show_form(
            step_id="esphome_configure",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "device_name": self._esphome_selected_name or "",
                "device_id": self._esphome_selected_device_id or "",
            },
        )

    async def async_step_bluetooth_device(self, user_input=None) -> ConfigFlowResult:
        """Select a Bluetooth device to add to monitoring (main config flow)."""
        entries = self._async_current_entries()
        bluetooth_entry = next(
            (e for e in entries if e.unique_id == self.ENTRY_UNIQUE_IDS["bluetooth"]),
            None,
        )
        existing_addresses = {
            t.get(CONF_BLUETOOTH_ADDRESS)
            for t in (
                bluetooth_entry.data.get(CONF_TARGETS, []) if bluetooth_entry else []
            )
            if t.get(CONF_BLUETOOTH_ADDRESS)
        }

        bluetooth_devices = await async_get_bluetooth_devices(self.hass)
        if not bluetooth_devices:
            return self.async_show_form(
                step_id="bluetooth_device",
                errors={"base": "no_bluetooth_devices"},
                data_schema=vol.Schema({}),
            )

        available = [
            d for d in bluetooth_devices if d["bt_address"] not in existing_addresses
        ]
        if not available:
            return self.async_show_form(
                step_id="bluetooth_device",
                errors={"base": "all_bluetooth_devices_added"},
                data_schema=vol.Schema({}),
            )

        if user_input is not None:
            self._bluetooth_selected_address = user_input[CONF_BLUETOOTH_ADDRESS]
            matched = next(
                (
                    d
                    for d in bluetooth_devices
                    if d["bt_address"] == self._bluetooth_selected_address
                ),
                {},
            )
            self._bluetooth_selected_name = (
                matched.get("name") or self._bluetooth_selected_address
            )
            self._bluetooth_selected_model = matched.get("model")
            self._bluetooth_selected_manufacturer = matched.get("manufacturer")
            return await self.async_step_bluetooth_configure()

        device_choices = {
            d["bt_address"]: (
                f"{d['name']} ({d['bt_address']})"
                + (f" RSSI {d['rssi']} dBm" if d.get("rssi") is not None else "")
            )
            for d in sorted(available, key=lambda x: x["name"].lower())
        }
        return self.async_show_form(
            step_id="bluetooth_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BLUETOOTH_ADDRESS): vol.In(device_choices),
                }
            ),
        )

    async def async_step_bluetooth_configure(self, user_input=None) -> ConfigFlowResult:
        """Set device name and alert settings for the selected Bluetooth device."""
        entries = self._async_current_entries()

        if user_input is not None:
            device_name = (
                user_input.get("device_name") or ""
            ).strip() or self._bluetooth_selected_name
            alerts_enabled = user_input.get(CONF_ALERTS_ENABLED, False)
            action_enabled = user_input.get(CONF_ALERT_ACTION_ENABLED, False)
            new_target = {
                CONF_PROTOCOL: PROTOCOL_BLUETOOTH,
                CONF_HOST: f"bluetooth:{self._bluetooth_selected_address}",
                CONF_BLUETOOTH_ADDRESS: self._bluetooth_selected_address,
                "device_name": device_name,
                CONF_ALERT_GROUP: (
                    user_input.get(CONF_ALERT_GROUP, "") or DEFAULT_ALERT_GROUP
                )
                if alerts_enabled
                else DEFAULT_ALERT_GROUP,
                CONF_ALERT_DELAY: user_input.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY),
                CONF_ALERT_ACTION: (user_input.get(CONF_ALERT_ACTION, "") or "")
                if action_enabled
                else "",
                CONF_ALERT_ACTION_DELAY: user_input.get(
                    CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
                ),
            }
            if self._bluetooth_selected_model:
                new_target["model"] = self._bluetooth_selected_model
            if self._bluetooth_selected_manufacturer:
                new_target["manufacturer"] = self._bluetooth_selected_manufacturer

            targets = list(self._data.get(CONF_TARGETS, []))
            targets.append(new_target)
            self._data[CONF_TARGETS] = targets
            self._data[CONF_PROTOCOL] = PROTOCOL_BLUETOOTH

            if not entries:
                return await self.async_step_dns()
            return await self.async_step_finish()

        notify_groups = await self._async_get_notify_groups()
        alert_actions = await self._async_get_alert_actions()
        schema = {
            vol.Optional(
                "device_name", default=self._bluetooth_selected_name or ""
            ): str,
            vol.Optional(CONF_ALERTS_ENABLED, default=False): bool,
            vol.Required(CONF_ALERT_DELAY, default=DEFAULT_ALERT_DELAY): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
        }
        if notify_groups:
            notify_groups_dict = {k: f"notify.{v}" for k, v in notify_groups.items()}
            notify_groups_dict[""] = "No alert group"
            schema[vol.Optional(CONF_ALERT_GROUP, default="")] = vol.In(
                notify_groups_dict
            )
        schema[vol.Optional(CONF_ALERT_ACTION_ENABLED, default=False)] = bool
        schema[
            vol.Required(CONF_ALERT_ACTION_DELAY, default=DEFAULT_ALERT_ACTION_DELAY)
        ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=120))
        if alert_actions:
            actions_dict = {"": "No action"}
            actions_dict.update(alert_actions)
            schema[vol.Optional(CONF_ALERT_ACTION, default="")] = vol.In(actions_dict)

        return self.async_show_form(
            step_id="bluetooth_configure",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "device_name": self._bluetooth_selected_name or "",
                "bt_address": self._bluetooth_selected_address or "",
            },
        )

    async def async_step_dns(self, user_input=None) -> ConfigFlowResult:
        """Handle DNS server configuration."""
        errors = {}

        if user_input is not None:
            dns_server = user_input[CONF_DNS_SERVER]
            if is_valid_ip(dns_server):
                self._data[CONF_DNS_SERVER] = dns_server
                if (
                    not self._async_current_entries()
                    and self._data.get(CONF_PROTOCOL) in NETWORK_PROTOCOLS
                    and not await self._async_validate_network_target()
                ):
                    errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_interval()
            else:
                errors["base"] = "invalid_dns_server"

        return self.async_show_form(
            step_id="dns",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DNS_SERVER, default=DEFAULT_DNS_SERVER): str,
                }
            ),
            errors=errors,
            description_placeholders={"default_dns": DEFAULT_DNS_SERVER},
        )

    async def async_step_interval(self, user_input=None) -> ConfigFlowResult:
        """Handle setting the update interval."""
        if user_input is not None:
            self._data[CONF_INTERVAL] = user_input[CONF_INTERVAL]
            return await self.async_step_finish()

        return self.async_show_form(
            step_id="interval",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
                        vol.Coerce(int), vol.Range(min=5, max=300)
                    ),
                }
            ),
        )

    async def async_step_port(self, user_input=None) -> ConfigFlowResult:
        """Handle port configuration."""
        errors = {}

        if user_input is not None:
            self._data.update(user_input)
            if not self._async_current_entries():
                return await self.async_step_dns()
            if not await self._async_validate_network_target():
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_finish()

        return self.async_show_form(
            step_id="port",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_finish(self, user_input=None) -> ConfigFlowResult:
        """Create or update the correct typed config entry."""
        entries = self._async_current_entries()

        # Determine which typed entry this device belongs to
        protocol = self._data.get(CONF_PROTOCOL)
        if protocol == PROTOCOL_ZHA:
            entry_type = "zha"
        elif protocol == PROTOCOL_MATTER:
            entry_type = "matter"
        elif protocol == PROTOCOL_ESPHOME:
            entry_type = "esphome"
        elif protocol == PROTOCOL_BLUETOOTH:
            entry_type = "bluetooth"
        else:
            entry_type = "network"

        unique_id = self.ENTRY_UNIQUE_IDS[entry_type]

        # Find the existing typed entry for this type (if any)
        typed_entry = next((e for e in entries if e.unique_id == unique_id), None)

        if entry_type == "network":
            device_name = (
                self._data.get("device_name", "").strip() or self._data[CONF_HOST]
            )
            targets = list(typed_entry.data[CONF_TARGETS]) if typed_entry else []

            base_target = {
                CONF_HOST: self._data[CONF_HOST],
                CONF_PROTOCOL: self._data[CONF_PROTOCOL],
                "device_name": device_name,
                CONF_ALERT_GROUP: self._data.get(CONF_ALERT_GROUP, DEFAULT_ALERT_GROUP),
                CONF_ALERT_DELAY: self._data.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY),
                CONF_ALERT_ACTION: self._data.get(CONF_ALERT_ACTION, ""),
                CONF_ALERT_ACTION_DELAY: self._data.get(
                    CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
                ),
            }

            if self._data[CONF_PROTOCOL] == PROTOCOL_AD_DC:
                for port in AD_DC_PORTS:
                    target = base_target.copy()
                    target[CONF_PROTOCOL] = PROTOCOL_TCP
                    target[CONF_PORT] = port
                    targets.append(target)
            else:
                if self._data[CONF_PROTOCOL] in [PROTOCOL_TCP, PROTOCOL_UDP]:
                    base_target[CONF_PORT] = self._data[CONF_PORT]
                targets.append(base_target)
        else:
            # ZHA / Matter: new target was already appended in the configure step.
            # Merge with any existing targets already stored in the typed entry.
            new_items = list(self._data.get(CONF_TARGETS, []))
            if typed_entry:
                existing = list(typed_entry.data[CONF_TARGETS])
                if entry_type == "zha":
                    existing_keys = {t.get(CONF_ZHA_IEEE) for t in existing}
                    existing.extend(
                        t
                        for t in new_items
                        if t.get(CONF_ZHA_IEEE) not in existing_keys
                    )
                elif entry_type == "matter":
                    existing_keys = {t.get(CONF_MATTER_NODE_ID) for t in existing}
                    existing.extend(
                        t
                        for t in new_items
                        if t.get(CONF_MATTER_NODE_ID) not in existing_keys
                    )
                elif entry_type == "esphome":
                    existing_keys = {t.get(CONF_ESPHOME_DEVICE_ID) for t in existing}
                    existing.extend(
                        t
                        for t in new_items
                        if t.get(CONF_ESPHOME_DEVICE_ID) not in existing_keys
                    )
                else:  # bluetooth
                    existing_keys = {t.get(CONF_BLUETOOTH_ADDRESS) for t in existing}
                    existing.extend(
                        t
                        for t in new_items
                        if t.get(CONF_BLUETOOTH_ADDRESS) not in existing_keys
                    )
                targets = existing
            else:
                targets = new_items

        data = {
            CONF_TARGETS: targets,
            CONF_INTERVAL: self._data.get(CONF_INTERVAL, DEFAULT_INTERVAL),
            CONF_DNS_SERVER: self._data.get(CONF_DNS_SERVER, DEFAULT_DNS_SERVER),
        }

        if typed_entry:
            self.hass.config_entries.async_update_entry(typed_entry, data=data)
            await self.hass.config_entries.async_reload(typed_entry.entry_id)
            return self.async_abort(reason="device_added")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self.ENTRY_TITLES[entry_type],
            data=data,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow."""

    ENTRY_TYPES_BY_UNIQUE_ID = {
        ConnectivityMonitorConfigFlow.ENTRY_UNIQUE_IDS["network"]: "network",
        ConnectivityMonitorConfigFlow.ENTRY_UNIQUE_IDS["zha"]: "zha",
        ConnectivityMonitorConfigFlow.ENTRY_UNIQUE_IDS["matter"]: "matter",
        ConnectivityMonitorConfigFlow.ENTRY_UNIQUE_IDS["esphome"]: "esphome",
        ConnectivityMonitorConfigFlow.ENTRY_UNIQUE_IDS["bluetooth"]: "bluetooth",
    }

    def __init__(self) -> None:
        """Initialize options flow."""
        self.config_data: dict = {}
        self._targets: list = []
        self._selected_device = None
        # ZHA device selection state
        self._zha_selected_ieee: str | None = None
        self._zha_selected_name: str | None = None
        self._zha_selected_model: str | None = None
        self._zha_selected_manufacturer: str | None = None
        # Matter device selection state
        self._matter_selected_node_id: str | None = None
        self._matter_selected_name: str | None = None
        self._matter_selected_model: str | None = None
        self._matter_selected_manufacturer: str | None = None
        # ESPHome device selection state
        self._esphome_selected_device_id: str | None = None
        # Bluetooth device selection state
        self._bluetooth_selected_address: str | None = None

    async def _async_get_notify_groups(self):
        """Get list of notification groups from Home Assistant."""
        notify_services = self.hass.services.async_services().get("notify", {})
        return {name: name.replace("notify.", "") for name in notify_services}

    async def _async_get_alert_actions(self):
        """Get available automations and scripts that can be triggered as alert actions."""
        actions = {}
        for state in self.hass.states.async_all():
            entity_id = state.entity_id
            domain = entity_id.split(".")[0]
            if domain in ("automation", "script"):
                name = state.attributes.get("friendly_name") or entity_id
                actions[entity_id] = f"{name} ({entity_id})"
        return dict(sorted(actions.items(), key=lambda x: x[1].lower()))

    def _get_entry_type(self) -> str:
        """Determine the typed config entry this options flow is editing."""
        entry_type = self.ENTRY_TYPES_BY_UNIQUE_ID.get(
            self.config_entry.unique_id or ""
        )
        if entry_type is not None:
            return entry_type

        if any(t.get(CONF_PROTOCOL) == PROTOCOL_ZHA for t in self._targets):
            return "zha"
        if any(t.get(CONF_PROTOCOL) == PROTOCOL_MATTER for t in self._targets):
            return "matter"
        if any(t.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME for t in self._targets):
            return "esphome"
        if any(t.get(CONF_PROTOCOL) == PROTOCOL_BLUETOOTH for t in self._targets):
            return "bluetooth"
        return "network"

    def _get_menu_actions(self) -> dict[str, str]:
        """Build the top-level options menu for the current entry type."""
        entry_type = self._get_entry_type()
        common_actions = {"settings": "General Settings"}

        if entry_type == "network":
            return {
                "rename": "Change Host / Device Name",
                "alerts": "Modify Alert Settings",
                "remove_device": "Remove Device",
                "remove_sensor": "Remove Single Sensor",
                **common_actions,
            }

        return {
            "alerts": "Modify Alert Settings",
            "remove_device": "Remove Device",
            **common_actions,
        }

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options."""
        self.config_data = dict(self.config_entry.data)
        self._targets = list(self.config_data[CONF_TARGETS])
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None) -> ConfigFlowResult:
        """Show the top-level action menu."""
        if user_input is not None:
            action = user_input["action"]
            entry_type = self._get_entry_type()

            if action == "rename":
                return await self.async_step_rename_device_select()
            if action == "alerts":
                if entry_type == "network":
                    return await self.async_step_device_select()
                if entry_type == "zha":
                    return await self.async_step_zha_alert_select()
                if entry_type == "matter":
                    return await self.async_step_matter_alert_select()
                if entry_type == "esphome":
                    return await self.async_step_esphome_alert_select()
                if entry_type == "bluetooth":
                    return await self.async_step_bluetooth_alert_select()
            elif action == "remove_device":
                if entry_type == "network":
                    return await self.async_step_remove_device()
                if entry_type == "zha":
                    return await self.async_step_remove_zha_device()
                if entry_type == "matter":
                    return await self.async_step_remove_matter_device()
                if entry_type == "esphome":
                    return await self.async_step_remove_esphome_device()
                if entry_type == "bluetooth":
                    return await self.async_step_remove_bluetooth_device()
            elif action == "remove_sensor":
                return await self.async_step_remove_sensor()
            elif action == "settings":
                return await self.async_step_settings_menu()

        actions = self._get_menu_actions()

        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(actions),
                }
            ),
        )

    async def async_step_settings_menu(self, user_input=None) -> ConfigFlowResult:
        """Show settings-related actions."""
        if user_input is not None:
            action = user_input["action"]
            if action == "general":
                return await self.async_step_settings()
            if action == "cleanup":
                return await self.async_step_cleanup_orphans()

        return self.async_show_form(
            step_id="settings_menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "general": "Modify General Settings",
                            "cleanup": "Clean up Orphaned Devices",
                        }
                    ),
                }
            ),
        )

    async def async_step_network_menu(self, user_input=None) -> ConfigFlowResult:
        """Show the Network Device sub-menu."""
        if user_input is not None:
            action = user_input["action"]
            if action == "rename":
                return await self.async_step_rename_device_select()
            if action == "alerts":
                return await self.async_step_device_select()
            if action == "remove_device":
                return await self.async_step_remove_device()
            if action == "remove_sensor":
                return await self.async_step_remove_sensor()

        return self.async_show_form(
            step_id="network_menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "rename": "Change Host / Device Name",
                            "alerts": "Modify Alert Settings",
                            "remove_device": "Remove Device",
                            "remove_sensor": "Remove Single Sensor",
                        }
                    ),
                }
            ),
        )

    async def async_step_zha_menu(self, user_input=None) -> ConfigFlowResult:
        """Show the ZigBee (ZHA) Device sub-menu."""
        if user_input is not None:
            action = user_input["action"]
            if action == "timeout":
                return await self.async_step_zha_select_for_timeout()
            if action == "alerts":
                return await self.async_step_zha_alert_select()
            if action == "remove":
                return await self.async_step_remove_zha_device()

        return self.async_show_form(
            step_id="zha_menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "timeout": "Change Inactivity Timeout",
                            "alerts": "Modify Alert Settings",
                            "remove": "Remove Device",
                        }
                    ),
                }
            ),
        )

    async def async_step_matter_menu(self, user_input=None) -> ConfigFlowResult:
        """Show the Matter Device sub-menu."""
        if user_input is not None:
            action = user_input["action"]
            if action == "alerts":
                return await self.async_step_matter_alert_select()
            if action == "remove":
                return await self.async_step_remove_matter_device()

        return self.async_show_form(
            step_id="matter_menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "alerts": "Modify Alert Settings",
                            "remove": "Remove Device",
                        }
                    ),
                }
            ),
        )

    async def async_step_matter_alert_select(self, user_input=None) -> ConfigFlowResult:
        """Select which Matter device to configure alerts for."""
        matter_targets = [
            t for t in self._targets if t.get(CONF_PROTOCOL) == PROTOCOL_MATTER
        ]
        if not matter_targets:
            return await self.async_step_menu()

        if user_input is not None:
            self._matter_selected_node_id = user_input["node_id"]
            return await self.async_step_matter_alert_config()

        devices = {
            t[
                CONF_MATTER_NODE_ID
            ]: f"{t.get('device_name', t[CONF_MATTER_NODE_ID])} ({t[CONF_MATTER_NODE_ID]})"
            for t in sorted(matter_targets, key=lambda x: x.get("device_name", ""))
        }
        return self.async_show_form(
            step_id="matter_alert_select",
            data_schema=vol.Schema(
                {
                    vol.Required("node_id"): vol.In(devices),
                }
            ),
        )

    async def async_step_matter_alert_config(self, user_input=None) -> ConfigFlowResult:
        """Configure alert settings for the selected Matter device."""
        notify_groups = await self._async_get_notify_groups()
        alert_actions = await self._async_get_alert_actions()

        current_target: dict[str, Any] = next(
            (
                t
                for t in self._targets
                if t.get(CONF_PROTOCOL) == PROTOCOL_MATTER
                and t.get(CONF_MATTER_NODE_ID) == self._matter_selected_node_id
            ),
            {},
        )
        current_alert_group = current_target.get(CONF_ALERT_GROUP, "")
        current_alert_delay = current_target.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY)
        current_alerts_enabled = bool(current_alert_group)
        current_alert_action = current_target.get(CONF_ALERT_ACTION, "")
        current_action_delay = current_target.get(
            CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
        )
        current_action_enabled = bool(current_alert_action)

        if user_input is not None:
            alerts_enabled = user_input.get(CONF_ALERTS_ENABLED, False)
            alert_group = user_input.get(CONF_ALERT_GROUP, "") if alerts_enabled else ""
            action_enabled = user_input.get(CONF_ALERT_ACTION_ENABLED, False)
            alert_action = (
                user_input.get(CONF_ALERT_ACTION, "") if action_enabled else ""
            )
            for t in self._targets:
                if (
                    t.get(CONF_PROTOCOL) == PROTOCOL_MATTER
                    and t.get(CONF_MATTER_NODE_ID) == self._matter_selected_node_id
                ):
                    if alert_group:
                        t[CONF_ALERT_GROUP] = alert_group
                    else:
                        t.pop(CONF_ALERT_GROUP, None)
                    t[CONF_ALERT_DELAY] = user_input[CONF_ALERT_DELAY]
                    if alert_action:
                        t[CONF_ALERT_ACTION] = alert_action
                    else:
                        t.pop(CONF_ALERT_ACTION, None)
                    t[CONF_ALERT_ACTION_DELAY] = user_input[CONF_ALERT_ACTION_DELAY]

            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        notify_groups_dict = {k: f"notify.{v}" for k, v in notify_groups.items()}
        notify_groups_dict[""] = "No alert group"
        schema = {
            vol.Optional(CONF_ALERTS_ENABLED, default=current_alerts_enabled): bool,
            vol.Optional(CONF_ALERT_GROUP, default=current_alert_group): vol.In(
                notify_groups_dict
            ),
            vol.Required(CONF_ALERT_DELAY, default=current_alert_delay): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
            vol.Optional(
                CONF_ALERT_ACTION_ENABLED, default=current_action_enabled
            ): bool,
            vol.Required(
                CONF_ALERT_ACTION_DELAY, default=current_action_delay
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
        }
        if alert_actions:
            actions_dict = {"": "No action"}
            actions_dict.update(alert_actions)
            schema[vol.Optional(CONF_ALERT_ACTION, default=current_alert_action)] = (
                vol.In(actions_dict)
            )
        return self.async_show_form(
            step_id="matter_alert_config",
            data_schema=vol.Schema(schema),
        )

    async def async_step_remove_matter_device(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Remove a monitored Matter device."""
        entity_registry = er.async_get(self.hass)

        matter_targets = [
            t for t in self._targets if t.get(CONF_PROTOCOL) == PROTOCOL_MATTER
        ]
        if not matter_targets:
            return await self.async_step_menu()

        if user_input is not None:
            node_id = user_input["node_id"]

            # Remove from targets list
            self._targets = [
                t
                for t in self._targets
                if not (
                    t.get(CONF_PROTOCOL) == PROTOCOL_MATTER
                    and t.get(CONF_MATTER_NODE_ID) == node_id
                )
            ]

            # Remove only our monitoring entity — the Matter device itself stays
            node_id_clean = node_id.replace("-", "_").replace(":", "_")
            unique_id = f"connectivity_matter_{node_id_clean}"
            entry_entities = er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            )
            for entity_entry in entry_entities:
                if entity_entry.unique_id == unique_id:
                    entity_registry.async_remove(entity_entry.entity_id)
                    break

            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        devices = {
            t[
                CONF_MATTER_NODE_ID
            ]: f"{t.get('device_name', t[CONF_MATTER_NODE_ID])} ({t[CONF_MATTER_NODE_ID]})"
            for t in sorted(matter_targets, key=lambda x: x.get("device_name", ""))
        }
        return self.async_show_form(
            step_id="remove_matter_device",
            data_schema=vol.Schema(
                {
                    vol.Required("node_id"): vol.In(devices),
                }
            ),
        )

    async def async_step_esphome_menu(self, user_input=None) -> ConfigFlowResult:
        """Show the ESPHome Device sub-menu."""
        if user_input is not None:
            action = user_input["action"]
            if action == "alerts":
                return await self.async_step_esphome_alert_select()
            if action == "remove":
                return await self.async_step_remove_esphome_device()

        return self.async_show_form(
            step_id="esphome_menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "alerts": "Modify Alert Settings",
                            "remove": "Remove Device",
                        }
                    ),
                }
            ),
        )

    async def async_step_bluetooth_menu(self, user_input=None) -> ConfigFlowResult:
        """Show the Bluetooth Device sub-menu."""
        if user_input is not None:
            action = user_input["action"]
            if action == "alerts":
                return await self.async_step_bluetooth_alert_select()
            if action == "remove":
                return await self.async_step_remove_bluetooth_device()

        return self.async_show_form(
            step_id="bluetooth_menu",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "alerts": "Modify Alert Settings",
                            "remove": "Remove Device",
                        }
                    ),
                }
            ),
        )

    async def async_step_bluetooth_alert_select(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Select which Bluetooth device to configure alerts for."""
        bluetooth_targets = [
            t for t in self._targets if t.get(CONF_PROTOCOL) == PROTOCOL_BLUETOOTH
        ]
        if not bluetooth_targets:
            return await self.async_step_menu()

        if user_input is not None:
            self._bluetooth_selected_address = user_input["bt_address"]
            return await self.async_step_bluetooth_alert_config()

        devices = {
            t[
                CONF_BLUETOOTH_ADDRESS
            ]: f"{t.get('device_name', t[CONF_BLUETOOTH_ADDRESS])} ({t[CONF_BLUETOOTH_ADDRESS]})"
            for t in sorted(bluetooth_targets, key=lambda x: x.get("device_name", ""))
        }
        return self.async_show_form(
            step_id="bluetooth_alert_select",
            data_schema=vol.Schema(
                {
                    vol.Required("bt_address"): vol.In(devices),
                }
            ),
        )

    async def async_step_bluetooth_alert_config(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Configure alert settings for the selected Bluetooth device."""
        notify_groups = await self._async_get_notify_groups()
        alert_actions = await self._async_get_alert_actions()

        current_target: dict[str, Any] = next(
            (
                t
                for t in self._targets
                if t.get(CONF_PROTOCOL) == PROTOCOL_BLUETOOTH
                and t.get(CONF_BLUETOOTH_ADDRESS) == self._bluetooth_selected_address
            ),
            {},
        )
        current_alert_group = current_target.get(CONF_ALERT_GROUP, "")
        current_alert_delay = current_target.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY)
        current_alerts_enabled = bool(current_alert_group)
        current_alert_action = current_target.get(CONF_ALERT_ACTION, "")
        current_action_delay = current_target.get(
            CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
        )
        current_action_enabled = bool(current_alert_action)

        if user_input is not None:
            alerts_enabled = user_input.get(CONF_ALERTS_ENABLED, False)
            alert_group = user_input.get(CONF_ALERT_GROUP, "") if alerts_enabled else ""
            action_enabled = user_input.get(CONF_ALERT_ACTION_ENABLED, False)
            alert_action = (
                user_input.get(CONF_ALERT_ACTION, "") if action_enabled else ""
            )
            for t in self._targets:
                if (
                    t.get(CONF_PROTOCOL) == PROTOCOL_BLUETOOTH
                    and t.get(CONF_BLUETOOTH_ADDRESS)
                    == self._bluetooth_selected_address
                ):
                    if alert_group:
                        t[CONF_ALERT_GROUP] = alert_group
                    else:
                        t.pop(CONF_ALERT_GROUP, None)
                    t[CONF_ALERT_DELAY] = user_input[CONF_ALERT_DELAY]
                    if alert_action:
                        t[CONF_ALERT_ACTION] = alert_action
                    else:
                        t.pop(CONF_ALERT_ACTION, None)
                    t[CONF_ALERT_ACTION_DELAY] = user_input[CONF_ALERT_ACTION_DELAY]

            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        notify_groups_dict = {k: f"notify.{v}" for k, v in notify_groups.items()}
        notify_groups_dict[""] = "No alert group"
        schema = {
            vol.Optional(CONF_ALERTS_ENABLED, default=current_alerts_enabled): bool,
            vol.Optional(CONF_ALERT_GROUP, default=current_alert_group): vol.In(
                notify_groups_dict
            ),
            vol.Required(CONF_ALERT_DELAY, default=current_alert_delay): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
            vol.Optional(
                CONF_ALERT_ACTION_ENABLED, default=current_action_enabled
            ): bool,
            vol.Required(
                CONF_ALERT_ACTION_DELAY, default=current_action_delay
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
        }
        if alert_actions:
            actions_dict = {"": "No action"}
            actions_dict.update(alert_actions)
            schema[vol.Optional(CONF_ALERT_ACTION, default=current_alert_action)] = (
                vol.In(actions_dict)
            )
        return self.async_show_form(
            step_id="bluetooth_alert_config",
            data_schema=vol.Schema(schema),
        )

    async def async_step_remove_bluetooth_device(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Remove a monitored Bluetooth device."""
        entity_registry = er.async_get(self.hass)

        bluetooth_targets = [
            t for t in self._targets if t.get(CONF_PROTOCOL) == PROTOCOL_BLUETOOTH
        ]
        if not bluetooth_targets:
            return await self.async_step_menu()

        if user_input is not None:
            bt_address = user_input["bt_address"]

            self._targets = [
                t
                for t in self._targets
                if not (
                    t.get(CONF_PROTOCOL) == PROTOCOL_BLUETOOTH
                    and t.get(CONF_BLUETOOTH_ADDRESS) == bt_address
                )
            ]

            bt_address_clean = bt_address.replace("-", "_").replace(":", "_")
            unique_id = f"connectivity_bluetooth_{bt_address_clean}"
            entry_entities = er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            )
            for entity_entry in entry_entities:
                if entity_entry.unique_id == unique_id:
                    entity_registry.async_remove(entity_entry.entity_id)
                    break

            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        devices = {
            t[
                CONF_BLUETOOTH_ADDRESS
            ]: f"{t.get('device_name', t[CONF_BLUETOOTH_ADDRESS])} ({t[CONF_BLUETOOTH_ADDRESS]})"
            for t in sorted(bluetooth_targets, key=lambda x: x.get("device_name", ""))
        }
        return self.async_show_form(
            step_id="remove_bluetooth_device",
            data_schema=vol.Schema(
                {
                    vol.Required("bt_address"): vol.In(devices),
                }
            ),
        )

    async def async_step_esphome_alert_select(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Select which ESPHome device to configure alerts for."""
        esphome_targets = [
            t for t in self._targets if t.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME
        ]
        if not esphome_targets:
            return await self.async_step_menu()

        if user_input is not None:
            self._esphome_selected_device_id = user_input["device_id"]
            return await self.async_step_esphome_alert_config()

        devices = {
            t[
                CONF_ESPHOME_DEVICE_ID
            ]: f"{t.get('device_name', t[CONF_ESPHOME_DEVICE_ID])} ({t[CONF_ESPHOME_DEVICE_ID]})"
            for t in sorted(esphome_targets, key=lambda x: x.get("device_name", ""))
        }
        return self.async_show_form(
            step_id="esphome_alert_select",
            data_schema=vol.Schema(
                {
                    vol.Required("device_id"): vol.In(devices),
                }
            ),
        )

    async def async_step_esphome_alert_config(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Configure alert settings for the selected ESPHome device."""
        notify_groups = await self._async_get_notify_groups()
        alert_actions = await self._async_get_alert_actions()

        current_target: dict[str, Any] = next(
            (
                t
                for t in self._targets
                if t.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME
                and t.get(CONF_ESPHOME_DEVICE_ID) == self._esphome_selected_device_id
            ),
            {},
        )
        current_alert_group = current_target.get(CONF_ALERT_GROUP, "")
        current_alert_delay = current_target.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY)
        current_alerts_enabled = bool(current_alert_group)
        current_alert_action = current_target.get(CONF_ALERT_ACTION, "")
        current_action_delay = current_target.get(
            CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
        )
        current_action_enabled = bool(current_alert_action)

        if user_input is not None:
            alerts_enabled = user_input.get(CONF_ALERTS_ENABLED, False)
            alert_group = user_input.get(CONF_ALERT_GROUP, "") if alerts_enabled else ""
            action_enabled = user_input.get(CONF_ALERT_ACTION_ENABLED, False)
            alert_action = (
                user_input.get(CONF_ALERT_ACTION, "") if action_enabled else ""
            )
            for t in self._targets:
                if (
                    t.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME
                    and t.get(CONF_ESPHOME_DEVICE_ID)
                    == self._esphome_selected_device_id
                ):
                    if alert_group:
                        t[CONF_ALERT_GROUP] = alert_group
                    else:
                        t.pop(CONF_ALERT_GROUP, None)
                    t[CONF_ALERT_DELAY] = user_input[CONF_ALERT_DELAY]
                    if alert_action:
                        t[CONF_ALERT_ACTION] = alert_action
                    else:
                        t.pop(CONF_ALERT_ACTION, None)
                    t[CONF_ALERT_ACTION_DELAY] = user_input[CONF_ALERT_ACTION_DELAY]

            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        notify_groups_dict = {k: f"notify.{v}" for k, v in notify_groups.items()}
        notify_groups_dict[""] = "No alert group"
        schema = {
            vol.Optional(CONF_ALERTS_ENABLED, default=current_alerts_enabled): bool,
            vol.Optional(CONF_ALERT_GROUP, default=current_alert_group): vol.In(
                notify_groups_dict
            ),
            vol.Required(CONF_ALERT_DELAY, default=current_alert_delay): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
            vol.Optional(
                CONF_ALERT_ACTION_ENABLED, default=current_action_enabled
            ): bool,
            vol.Required(
                CONF_ALERT_ACTION_DELAY, default=current_action_delay
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
        }
        if alert_actions:
            actions_dict = {"": "No action"}
            actions_dict.update(alert_actions)
            schema[vol.Optional(CONF_ALERT_ACTION, default=current_alert_action)] = (
                vol.In(actions_dict)
            )
        return self.async_show_form(
            step_id="esphome_alert_config",
            data_schema=vol.Schema(schema),
        )

    async def async_step_remove_esphome_device(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Remove a monitored ESPHome device."""
        entity_registry = er.async_get(self.hass)

        esphome_targets = [
            t for t in self._targets if t.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME
        ]
        if not esphome_targets:
            return await self.async_step_menu()

        if user_input is not None:
            device_id = user_input["device_id"]

            # Remove from targets list
            self._targets = [
                t
                for t in self._targets
                if not (
                    t.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME
                    and t.get(CONF_ESPHOME_DEVICE_ID) == device_id
                )
            ]

            # Remove only our monitoring entity — the ESPHome device stays
            device_id_clean = device_id.replace("-", "_").replace(":", "_")
            unique_id = f"connectivity_esphome_{device_id_clean}"
            entry_entities = er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            )
            for entity_entry in entry_entities:
                if entity_entry.unique_id == unique_id:
                    entity_registry.async_remove(entity_entry.entity_id)
                    break

            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        devices = {
            t[
                CONF_ESPHOME_DEVICE_ID
            ]: f"{t.get('device_name', t[CONF_ESPHOME_DEVICE_ID])} ({t[CONF_ESPHOME_DEVICE_ID]})"
            for t in sorted(esphome_targets, key=lambda x: x.get("device_name", ""))
        }
        return self.async_show_form(
            step_id="remove_esphome_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device_id"): vol.In(devices),
                }
            ),
        )

    async def async_step_rename_device_select(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Select which device to rename (network devices only)."""
        devices = {}
        for target in self._targets:
            if target.get(CONF_PROTOCOL) in (
                PROTOCOL_ZHA,
                PROTOCOL_MATTER,
                PROTOCOL_ESPHOME,
                PROTOCOL_BLUETOOTH,
            ):
                continue  # Shared-registry devices don't support host renaming
            device_host = target[CONF_HOST]
            if device_host not in devices:
                device_name = target.get("device_name", device_host)
                devices[device_host] = device_name

        if user_input is not None:
            self._selected_device = user_input["device"]
            return await self.async_step_rename_host()

        return self.async_show_form(
            step_id="rename_device_select",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(
                        dict(
                            sorted(
                                {
                                    host: f"{name} ({host})"
                                    for host, name in devices.items()
                                }.items(),
                                key=lambda x: x[1].lower(),
                            )
                        )
                    )
                }
            ),
        )

    async def async_step_rename_host(self, user_input=None) -> ConfigFlowResult:
        """Enter the new host IP/FQDN and device name."""
        errors = {}

        # Find current device name for the selected device
        current_device_name = self._selected_device
        for target in self._targets:
            if target[CONF_HOST] == self._selected_device:
                current_device_name = target.get("device_name", self._selected_device)
                break

        if user_input is not None:
            new_host = user_input[CONF_HOST].strip()
            new_device_name = user_input.get("device_name", "").strip() or new_host

            if not new_host:
                errors[CONF_HOST] = "invalid_host"
            else:
                old_host = self._selected_device
                device_registry = dr.async_get(self.hass)

                # Locate device entries via hw_version, which is always set to
                # target[CONF_HOST] in DeviceInfo — works regardless of whether
                # the identifier uses a MAC or the host string.
                old_device_ids = set()
                for device_entry in device_registry.devices.values():
                    if device_entry.hw_version == old_host and any(
                        i[0] == DOMAIN for i in device_entry.identifiers
                    ):
                        old_device_ids.add(device_entry.id)

                # Update all targets that belong to the old host
                for target in self._targets:
                    if target[CONF_HOST] == old_host:
                        target[CONF_HOST] = new_host
                        target["device_name"] = new_device_name

                # Save updated config
                self.config_data[CONF_TARGETS] = self._targets
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=self.config_data
                )

                # Remove old device registry entries. Entity registry cleanup
                # is handled automatically by sensor.py during the reload below.
                for device_id in old_device_ids:
                    device_registry.async_remove_device(device_id)

                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="rename_host",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._selected_device): str,
                    vol.Optional("device_name", default=current_device_name): str,
                }
            ),
            errors=errors,
        )

    async def async_step_device_select(self, user_input=None) -> ConfigFlowResult:
        """First step of alert modification - device selection (network only)."""
        # Get unique devices (skip ZHA and Matter targets — they don't use notify groups)
        devices = {}
        for target in self._targets:
            if target.get(CONF_PROTOCOL) in (
                PROTOCOL_ZHA,
                PROTOCOL_MATTER,
                PROTOCOL_ESPHOME,
                PROTOCOL_BLUETOOTH,
            ):
                continue
            device_host = target[CONF_HOST]
            if device_host not in devices:
                device_name = target.get("device_name", device_host)
                devices[device_host] = {
                    "name": device_name,
                    "alert_group": target.get(CONF_ALERT_GROUP, DEFAULT_ALERT_GROUP),
                    "alert_delay": target.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY),
                }

        if user_input is not None:
            self._selected_device = user_input["device"]
            return await self.async_step_alert_config()

        return self.async_show_form(
            step_id="device_select",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(
                        dict(
                            sorted(
                                {
                                    host: f"{info['name']} ({host})"
                                    for host, info in devices.items()
                                }.items(),
                                key=lambda x: x[1].lower(),
                            )
                        )
                    )
                }
            ),
        )

    async def async_step_alert_config(self, user_input=None) -> ConfigFlowResult:
        """Second step of alert modification - alert settings configuration."""
        notify_groups = await self._async_get_notify_groups()
        alert_actions = await self._async_get_alert_actions()

        # Get current settings for selected device
        current_settings = None
        for target in self._targets:
            if target[CONF_HOST] == self._selected_device:
                current_settings = {
                    "alerts_enabled": bool(target.get(CONF_ALERT_GROUP, "")),
                    "alert_group": target.get(CONF_ALERT_GROUP, ""),
                    "alert_delay": target.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY),
                    "alert_action_enabled": bool(target.get(CONF_ALERT_ACTION, "")),
                    "alert_action": target.get(CONF_ALERT_ACTION, ""),
                    "alert_action_delay": target.get(
                        CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
                    ),
                }
                break

        if user_input is not None:
            # Update all targets for the selected device
            alerts_enabled = user_input.get(CONF_ALERTS_ENABLED, False)
            alert_group = user_input.get(CONF_ALERT_GROUP, "") if alerts_enabled else ""
            action_enabled = user_input.get(CONF_ALERT_ACTION_ENABLED, False)
            alert_action = (
                user_input.get(CONF_ALERT_ACTION, "") if action_enabled else ""
            )
            for target in self._targets:
                if target[CONF_HOST] == self._selected_device:
                    if alert_group:
                        target[CONF_ALERT_GROUP] = alert_group
                    else:
                        target.pop(CONF_ALERT_GROUP, None)
                    target[CONF_ALERT_DELAY] = user_input[CONF_ALERT_DELAY]
                    if alert_action:
                        target[CONF_ALERT_ACTION] = alert_action
                    else:
                        target.pop(CONF_ALERT_ACTION, None)
                    target[CONF_ALERT_ACTION_DELAY] = user_input[
                        CONF_ALERT_ACTION_DELAY
                    ]

            # Update config entry with modified targets
            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )

            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        # Create the selection form
        notify_groups_dict = {k: f"notify.{v}" for k, v in notify_groups.items()}
        notify_groups_dict[""] = "No alert group"

        schema = {
            vol.Optional(
                CONF_ALERTS_ENABLED,
                default=current_settings["alerts_enabled"]
                if current_settings
                else False,
            ): bool,
            vol.Optional(
                CONF_ALERT_GROUP,
                default=current_settings["alert_group"] if current_settings else "",
            ): vol.In(notify_groups_dict),
            vol.Required(
                CONF_ALERT_DELAY,
                default=current_settings["alert_delay"]
                if current_settings
                else DEFAULT_ALERT_DELAY,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            vol.Optional(
                CONF_ALERT_ACTION_ENABLED,
                default=current_settings["alert_action_enabled"]
                if current_settings
                else False,
            ): bool,
            vol.Required(
                CONF_ALERT_ACTION_DELAY,
                default=current_settings["alert_action_delay"]
                if current_settings
                else DEFAULT_ALERT_ACTION_DELAY,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
        }
        if alert_actions:
            actions_dict = {"": "No action"}
            actions_dict.update(alert_actions)
            schema[
                vol.Optional(
                    CONF_ALERT_ACTION,
                    default=current_settings["alert_action"]
                    if current_settings
                    else "",
                )
            ] = vol.In(actions_dict)

        return self.async_show_form(
            step_id="alert_config", data_schema=vol.Schema(schema)
        )

    async def async_step_remove_device(self, user_input=None) -> ConfigFlowResult:
        """Handle removing a complete device."""
        device_registry = dr.async_get(self.hass)

        if user_input is not None:
            device_host = user_input["device"]

            # Remove all targets for this device
            self._targets = [t for t in self._targets if t[CONF_HOST] != device_host]

            # Locate device entries via hw_version, which is always set to
            # target[CONF_HOST] in DeviceInfo for every network device — this
            # works regardless of whether the identifier uses a MAC or the host.
            device_ids = set()
            for device_entry in device_registry.devices.values():
                if device_entry.hw_version == device_host and any(
                    i[0] == DOMAIN for i in device_entry.identifiers
                ):
                    device_ids.add(device_entry.id)

            # Remove devices — HA automatically removes their associated entities
            # from the entity registry; any remaining stale entities are cleaned up
            # during the reload triggered below.
            for device_id in device_ids:
                device_registry.async_remove_device(device_id)

            # Update config entry
            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )

            # Reload the config entry
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        # Get unique network devices (ZHA/Matter/ESPHome devices are removed via their own step)
        devices = {}
        for target in self._targets:
            if target.get(CONF_PROTOCOL) in (
                PROTOCOL_ZHA,
                PROTOCOL_MATTER,
                PROTOCOL_ESPHOME,
                PROTOCOL_BLUETOOTH,
            ):
                continue
            device_name = target.get("device_name", target[CONF_HOST])
            devices[target[CONF_HOST]] = device_name

        if not devices:
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="remove_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(
                        dict(
                            sorted(
                                {
                                    host: f"{name} ({host})"
                                    for host, name in devices.items()
                                }.items(),
                                key=lambda x: x[1].lower(),
                            )
                        )
                    )
                }
            ),
        )

    async def async_step_remove_sensor(self, user_input=None) -> ConfigFlowResult:
        """Handle removing a single sensor."""
        entity_registry = er.async_get(self.hass)

        if user_input is not None:
            sensor_id = user_input["sensor"]

            # Find and remove the specific sensor from targets
            for i, target in enumerate(self._targets):
                current_id = f"{target[CONF_HOST]}_{target[CONF_PROTOCOL]}_{target.get(CONF_PORT, 'ping')}"
                if current_id == sensor_id:
                    self._targets.pop(i)
                    break

            # Get all entities for this config entry
            entry_entities = er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            )

            # Find and remove the entity
            for entity_entry in entry_entities:
                if entity_entry.unique_id == sensor_id:
                    entity_registry.async_remove(entity_entry.entity_id)

            # Update config entry
            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )

            # Reload the config entry
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        # Create list of sensors with readable names (network sensors only)
        sensors = {}
        for target in self._targets:
            if target.get(CONF_PROTOCOL) in (
                PROTOCOL_ZHA,
                PROTOCOL_MATTER,
                PROTOCOL_ESPHOME,
                PROTOCOL_BLUETOOTH,
            ):
                continue  # Shared-registry devices are removed via their own steps
            device_name = target.get("device_name", target[CONF_HOST])
            if target[CONF_PROTOCOL] in [PROTOCOL_TCP, PROTOCOL_UDP]:
                sensor_name = (
                    f"{device_name} - {target[CONF_PROTOCOL]} {target[CONF_PORT]}"
                )
            else:
                sensor_name = f"{device_name} - {target[CONF_PROTOCOL]}"

            sensor_id = f"{target[CONF_HOST]}_{target[CONF_PROTOCOL]}_{target.get(CONF_PORT, 'ping')}"
            sensors[sensor_id] = sensor_name

        if not sensors:
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="remove_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required("sensor"): vol.In(
                        dict(sorted(sensors.items(), key=lambda x: x[1].lower()))
                    )
                }
            ),
        )

    async def async_step_modify_alerts(self, user_input=None) -> ConfigFlowResult:
        """Handle alert modifications."""
        notify_groups = await self._async_get_notify_groups()

        if not notify_groups:
            return self.async_show_form(
                step_id="modify_alerts",
                errors={"base": "no_notify_groups"},
                description_placeholders={"setup_link": "/config/integrations"},
            )

        # Get unique devices and their current alert settings
        devices = {}
        for target in self._targets:
            device_host = target[CONF_HOST]
            if device_host not in devices:
                device_name = target.get("device_name", device_host)
                devices[device_host] = {
                    "name": device_name,
                    "alert_group": target.get(CONF_ALERT_GROUP, DEFAULT_ALERT_GROUP),
                    "alert_delay": target.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY),
                }

        if user_input is not None:
            device_host = user_input["device"]
            selected_device = devices[device_host]

            # Update all targets for the selected device
            for target in self._targets:
                if target[CONF_HOST] == device_host:
                    target[CONF_ALERT_GROUP] = user_input[CONF_ALERT_GROUP]
                    target[CONF_ALERT_DELAY] = user_input[CONF_ALERT_DELAY]

            # Update config entry with modified targets
            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )

            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        schema = {
            vol.Required("device"): vol.In(
                dict(
                    sorted(
                        {
                            host: f"{info['name']} ({host})"
                            for host, info in devices.items()
                        }.items(),
                        key=lambda x: x[1].lower(),
                    )
                )
            ),
            vol.Optional(
                CONF_ALERT_GROUP,
                default=selected_device["alert_group"]
                if selected_device
                else DEFAULT_ALERT_GROUP,
            ): vol.In({k: f"notify.{v}" for k, v in notify_groups.items()}),
            vol.Required(
                CONF_ALERT_DELAY,
                default=selected_device["alert_delay"]
                if selected_device
                else DEFAULT_ALERT_DELAY,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
        }

        return self.async_show_form(
            step_id="modify_alerts", data_schema=vol.Schema(schema)
        )

    async def async_step_zha_alert_select(self, user_input=None) -> ConfigFlowResult:
        """Select which ZHA device to configure alerts for."""
        zha_targets = [t for t in self._targets if t.get(CONF_PROTOCOL) == PROTOCOL_ZHA]
        if not zha_targets:
            return await self.async_step_menu()

        if user_input is not None:
            self._zha_selected_ieee = user_input["ieee"]
            return await self.async_step_zha_alert_config()

        devices = {
            t[
                CONF_ZHA_IEEE
            ]: f"{t.get('device_name', t[CONF_ZHA_IEEE])} ({t[CONF_ZHA_IEEE]})"
            for t in sorted(zha_targets, key=lambda x: x.get("device_name", ""))
        }
        return self.async_show_form(
            step_id="zha_alert_select",
            data_schema=vol.Schema(
                {
                    vol.Required("ieee"): vol.In(devices),
                }
            ),
        )

    async def async_step_zha_alert_config(self, user_input=None) -> ConfigFlowResult:
        """Configure alert settings for the selected ZHA device."""
        notify_groups = await self._async_get_notify_groups()
        alert_actions = await self._async_get_alert_actions()

        current_target: dict[str, Any] = next(
            (
                t
                for t in self._targets
                if t.get(CONF_PROTOCOL) == PROTOCOL_ZHA
                and t.get(CONF_ZHA_IEEE) == self._zha_selected_ieee
            ),
            {},
        )
        current_alert_group = current_target.get(CONF_ALERT_GROUP, "")
        current_alert_delay = current_target.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY)
        current_alerts_enabled = bool(current_alert_group)
        current_alert_action = current_target.get(CONF_ALERT_ACTION, "")
        current_action_delay = current_target.get(
            CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
        )
        current_action_enabled = bool(current_alert_action)

        if user_input is not None:
            alerts_enabled = user_input.get(CONF_ALERTS_ENABLED, False)
            alert_group = user_input.get(CONF_ALERT_GROUP, "") if alerts_enabled else ""
            action_enabled = user_input.get(CONF_ALERT_ACTION_ENABLED, False)
            alert_action = (
                user_input.get(CONF_ALERT_ACTION, "") if action_enabled else ""
            )
            for t in self._targets:
                if (
                    t.get(CONF_PROTOCOL) == PROTOCOL_ZHA
                    and t.get(CONF_ZHA_IEEE) == self._zha_selected_ieee
                ):
                    if alert_group:
                        t[CONF_ALERT_GROUP] = alert_group
                    else:
                        t.pop(CONF_ALERT_GROUP, None)
                    t[CONF_ALERT_DELAY] = user_input[CONF_ALERT_DELAY]
                    if alert_action:
                        t[CONF_ALERT_ACTION] = alert_action
                    else:
                        t.pop(CONF_ALERT_ACTION, None)
                    t[CONF_ALERT_ACTION_DELAY] = user_input[CONF_ALERT_ACTION_DELAY]

            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        notify_groups_dict = {k: f"notify.{v}" for k, v in notify_groups.items()}
        notify_groups_dict[""] = "No alert group"
        schema = {
            vol.Optional(CONF_ALERTS_ENABLED, default=current_alerts_enabled): bool,
            vol.Optional(CONF_ALERT_GROUP, default=current_alert_group): vol.In(
                notify_groups_dict
            ),
            vol.Required(CONF_ALERT_DELAY, default=current_alert_delay): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
            vol.Optional(
                CONF_ALERT_ACTION_ENABLED, default=current_action_enabled
            ): bool,
            vol.Required(
                CONF_ALERT_ACTION_DELAY, default=current_action_delay
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
        }
        if alert_actions:
            actions_dict = {"": "No action"}
            actions_dict.update(alert_actions)
            schema[vol.Optional(CONF_ALERT_ACTION, default=current_alert_action)] = (
                vol.In(actions_dict)
            )
        return self.async_show_form(
            step_id="zha_alert_config",
            data_schema=vol.Schema(schema),
        )

    async def async_step_remove_zha_device(self, user_input=None) -> ConfigFlowResult:
        """Remove a monitored ZHA device."""
        entity_registry = er.async_get(self.hass)

        zha_targets = [t for t in self._targets if t.get(CONF_PROTOCOL) == PROTOCOL_ZHA]
        if not zha_targets:
            return await self.async_step_menu()

        if user_input is not None:
            ieee = user_input["ieee"]

            # Remove from targets list
            self._targets = [
                t
                for t in self._targets
                if not (
                    t.get(CONF_PROTOCOL) == PROTOCOL_ZHA
                    and t.get(CONF_ZHA_IEEE) == ieee
                )
            ]

            # Only remove our monitoring entity — the ZHA device itself is
            # owned by the ZHA integration and must NOT be removed.
            ieee_clean = ieee.replace(":", "").replace("-", "")
            unique_id = f"connectivity_zha_{ieee_clean}"
            entry_entities = er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            )
            for entity_entry in entry_entities:
                if entity_entry.unique_id == unique_id:
                    entity_registry.async_remove(entity_entry.entity_id)
                    break

            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        devices = {
            t[
                CONF_ZHA_IEEE
            ]: f"{t.get('device_name', t[CONF_ZHA_IEEE])} ({t[CONF_ZHA_IEEE]})"
            for t in sorted(zha_targets, key=lambda x: x.get("device_name", ""))
        }
        return self.async_show_form(
            step_id="remove_zha_device",
            data_schema=vol.Schema(
                {
                    vol.Required("ieee"): vol.In(devices),
                }
            ),
        )

    async def async_step_zha_select_for_timeout(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Select which ZHA device to change the inactivity timeout for."""
        zha_targets = [t for t in self._targets if t.get(CONF_PROTOCOL) == PROTOCOL_ZHA]
        if not zha_targets:
            return await self.async_step_menu()

        if user_input is not None:
            self._zha_selected_ieee = user_input["ieee"]
            return await self.async_step_zha_update_timeout()

        devices = {
            t[
                CONF_ZHA_IEEE
            ]: f"{t.get('device_name', t[CONF_ZHA_IEEE])} ({t[CONF_ZHA_IEEE]})"
            for t in sorted(zha_targets, key=lambda x: x.get("device_name", ""))
        }
        return self.async_show_form(
            step_id="zha_select_for_timeout",
            data_schema=vol.Schema(
                {
                    vol.Required("ieee"): vol.In(devices),
                }
            ),
        )

    async def async_step_zha_update_timeout(self, user_input=None) -> ConfigFlowResult:
        """Update the inactivity timeout for the selected ZHA device."""
        current_timeout = DEFAULT_INACTIVE_TIMEOUT
        for t in self._targets:
            if (
                t.get(CONF_PROTOCOL) == PROTOCOL_ZHA
                and t.get(CONF_ZHA_IEEE) == self._zha_selected_ieee
            ):
                current_timeout = t.get(CONF_INACTIVE_TIMEOUT, DEFAULT_INACTIVE_TIMEOUT)
                break

        if user_input is not None:
            for t in self._targets:
                if (
                    t.get(CONF_PROTOCOL) == PROTOCOL_ZHA
                    and t.get(CONF_ZHA_IEEE) == self._zha_selected_ieee
                ):
                    t[CONF_INACTIVE_TIMEOUT] = user_input[CONF_INACTIVE_TIMEOUT]

            self.config_data[CONF_TARGETS] = self._targets
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="zha_update_timeout",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INACTIVE_TIMEOUT, default=current_timeout
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
                }
            ),
        )

    async def async_step_settings(self, user_input=None) -> ConfigFlowResult:
        """Handle changing general settings."""
        if user_input is not None:
            self.config_data[CONF_INTERVAL] = user_input[CONF_INTERVAL]
            self.config_data[CONF_DNS_SERVER] = user_input[CONF_DNS_SERVER]

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        schema = {
            vol.Required(
                CONF_INTERVAL, default=self.config_data[CONF_INTERVAL]
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
            vol.Required(
                CONF_DNS_SERVER, default=self.config_data[CONF_DNS_SERVER]
            ): str,
        }

        return self.async_show_form(step_id="settings", data_schema=vol.Schema(schema))

    async def async_step_cleanup_orphans(self, user_input=None) -> ConfigFlowResult:
        """Remove devices registered under this integration that have no entities."""
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        entry_id = self.config_entry.entry_id

        removed = []
        for device_entry in list(device_registry.devices.values()):
            # Only consider devices that list our config entry
            if entry_id not in device_entry.config_entries:
                continue
            # Check whether any entity still belongs to our config entry
            entry_entities = [
                e
                for e in er.async_entries_for_device(entity_registry, device_entry.id)
                if e.config_entry_id == entry_id
            ]
            if not entry_entities:
                removed.append(device_entry.name or device_entry.id)
                if device_entry.config_entries == {entry_id}:
                    # Exclusively ours — delete the device entirely
                    device_registry.async_remove_device(device_entry.id)
                else:
                    # Shared with another integration — only remove our association
                    device_registry.async_update_device(
                        device_entry.id, remove_config_entry_id=entry_id
                    )

        if removed:
            _LOGGER.info(
                "Connectivity Monitor: cleaned up orphaned devices: %s", removed
            )

        return self.async_abort(reason="cleanup_done")
