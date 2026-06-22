"""Config flow for Mitsubishi Comfort integration."""

import logging
from typing import Any

from mitsubishi_comfort import MitsubishiCloudAccount
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_ADDRESSES, DOMAIN

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
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(account.user_id)
                self._abort_if_unique_id_configured()

                if not devices:
                    errors["base"] = "no_devices"
                else:
                    return self.async_create_entry(
                        title=f"Mitsubishi Comfort ({user_input[CONF_USERNAME]})",
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
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
        entry = next(
            (
                entry
                for entry in self._async_current_entries(include_ignore=False)
                if device is not None and entry.entry_id in device.config_entries
            ),
            None,
        )
        if entry is None:
            return self.async_abort(reason="already_configured")

        addresses = entry.data.get(CONF_ADDRESSES, {})
        if addresses.get(mac) != discovery_info.ip:
            self.hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_ADDRESSES: {**addresses, mac: discovery_info.ip},
                },
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_abort(reason="already_configured")
