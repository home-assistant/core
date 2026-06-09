"""Config flow for Mitsubishi Comfort integration."""

from ipaddress import ip_address
import logging
from typing import Any

from mitsubishi_comfort import MitsubishiCloudAccount
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_ADDRESSES, CONF_CREDENTIALS, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class MitsubishiComfortConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Mitsubishi Comfort."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return MitsubishiComfortOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            account = MitsubishiCloudAccount(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )

            devices: dict = {}
            try:
                await account.login()
                devices = await account.discover_devices()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except DeviceConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unexpected error discovering Mitsubishi Comfort devices"
                )
                errors["base"] = "unknown"
            else:
                _LOGGER.debug(
                    "Discovered %d device(s) for %s",
                    len(devices),
                    user_input[CONF_USERNAME],
                )

            if not errors:
                await self.async_set_unique_id(account.user_id)
                self._abort_if_unique_id_configured()

                if not devices:
                    errors["base"] = "no_devices"
                else:
                    # Persist the per-device credentials discovered here (the
                    # Socket.IO password fetch). async_setup_entry replays them
                    # via discover_devices(cached_credentials=...) so it never
                    # repeats that slow, rate-limited call.
                    return self.async_create_entry(
                        title=f"Mitsubishi Comfort ({user_input[CONF_USERNAME]})",
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_CREDENTIALS: {
                                serial: {
                                    "password": info.password,
                                    "crypto_serial": info.crypto_serial,
                                    "mac": info.mac,
                                }
                                for serial, info in devices.items()
                                if info.password and info.crypto_serial
                            },
                        },
                    )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a registered device discovered on the local network via DHCP.

        The cloud API never returns a device's LAN IP, so DHCP discovery is the
        source of addresses. Each device is registered with its MAC during setup,
        so "registered_devices" discovery only fires for our own devices: record
        the IP on the owning entry and reload to set the device up or recover a
        changed IP.
        """
        mac = dr.format_mac(discovery_info.macaddress)
        device = dr.async_get(self.hass).async_get_device(
            connections={(dr.CONNECTION_NETWORK_MAC, mac)}
        )
        if device is None:
            return self.async_abort(reason="already_configured")
        entry = next(
            (
                entry
                for entry in self._async_current_entries(include_ignore=False)
                if entry.entry_id in device.config_entries
            ),
            None,
        )
        if entry is None:
            return self.async_abort(reason="already_configured")

        addresses = entry.data.get(CONF_ADDRESSES, {})
        if addresses.get(mac) != discovery_info.ip:
            _LOGGER.debug("DHCP discovery resolved %s to %s", mac, discovery_info.ip)
            self.hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_ADDRESSES: {**addresses, mac: discovery_info.ip},
                },
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_abort(reason="already_configured")


class MitsubishiComfortOptionsFlow(OptionsFlow):
    """Let the user set a LAN IP per device the cloud cannot locate.

    The cloud never returns a device's LAN IP. DHCP discovery supplies it for
    devices on Home Assistant's own network segment, but cannot reach devices on
    another subnet/VLAN — for those the user enters the IP here.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage per-device LAN addresses."""
        addresses: dict[str, str] = dict(self.config_entry.data.get(CONF_ADDRESSES, {}))
        device_registry = dr.async_get(self.hass)
        # Map each device's formatted MAC (the address cache key) to its name.
        macs: dict[str, str] = {}
        for device in dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        ):
            mac = next(
                (
                    conn_id
                    for conn_type, conn_id in device.connections
                    if conn_type == dr.CONNECTION_NETWORK_MAC
                ),
                None,
            )
            if mac is not None:
                formatted = dr.format_mac(mac)
                macs[formatted] = device.name_by_user or device.name or formatted
        if not macs:
            return self.async_abort(reason="no_devices")

        errors: dict[str, str] = {}
        if user_input is not None:
            updated = dict(addresses)
            for mac in macs:
                value = user_input.get(mac, "").strip()
                if not value:
                    updated.pop(mac, None)
                    continue
                try:
                    ip_address(value)
                except ValueError:
                    errors["base"] = "invalid_ip"
                else:
                    updated[mac] = value
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_ADDRESSES: updated},
                )
                self.hass.config_entries.async_schedule_reload(
                    self.config_entry.entry_id
                )
                return self.async_create_entry(data={})

        # Pre-fill with the submitted values on a validation error so the user
        # does not lose what they typed; otherwise pre-fill the stored addresses.
        schema = vol.Schema({vol.Optional(mac): str for mac in macs})
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input if user_input is not None else addresses
            ),
            errors=errors,
            description_placeholders={"devices": ", ".join(macs.values())},
        )
