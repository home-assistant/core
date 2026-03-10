"""Config flow for WiiM integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from wiim.discovery import async_probe_wiim_device
from wiim.models import WiimProbeResult

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_UDN,
    CONF_UPNP_LOCATION,
    DOMAIN,
    LOGGER,
    UPNP_PORT,
    ZEROCONF_TYPE_LINKPLAY,
)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

VERSION = 1
MINOR_VERSION = 1


async def _validate_device_and_get_info(
    hass: HomeAssistant, host_or_udn: str, location: str | None = None
) -> WiimProbeResult:
    """Validate the given host or UDN can be reached and is a WiiM device.

    If location is provided, uses that directly for UPnP device creation.
    Otherwise, assumes host_or_udn is an IP and tries to discover UPnP info.
    Returns normalized device info for the config flow.
    """
    session = async_get_clientsession(hass)
    try:
        if location:
            LOGGER.debug("Validating UPnP device at location: %s", location)
            probe_result = await async_probe_wiim_device(
                location,
                session,
                host=host_or_udn,
            )
            if probe_result is None:
                raise CannotConnect("Could not determine device information via UPnP.")
            return probe_result
        if "uuid:" in host_or_udn.lower():
            raise CannotConnect(
                f"Validation by UDN ({host_or_udn}) alone is not supported for connection. Use IP/host or discovery."
            )
        LOGGER.debug(
            "No UPnP location provided for %s, attempting HTTP validation",
            host_or_udn,
        )

        raise CannotConnect("Could not determine device information via UPnP or HTTP.")
    except TimeoutError as err:
        LOGGER.warning(
            "Timeout while validating WiiM device at %s: %s",
            host_or_udn or location,
            err,
        )
        raise CannotConnect(f"Timeout connecting to device: {err}") from err


class WiimConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiiM."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_info: WiimProbeResult | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step when user adds integration manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                constructed_location = f"http://{host}:{UPNP_PORT}/description.xml"
                device_info = await _validate_device_and_get_info(
                    self.hass, host, location=constructed_location
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except (OSError, ValueError) as err:
                LOGGER.exception(
                    "Unexpected exception during user step validation for host %s: %s",
                    host,
                    err,
                )
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_info.udn)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: device_info.host,
                        CONF_UPNP_LOCATION: device_info.location,
                    }
                )
                entry_data = {
                    CONF_HOST: device_info.host,
                    CONF_UDN: device_info.udn,
                    CONF_UPNP_LOCATION: device_info.location,
                }
                return self.async_create_entry(title=device_info.name, data=entry_data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""
        LOGGER.debug(
            "Zeroconf discovery received: Name: %s, Host: %s, Port: %s, Properties: %s",
            discovery_info.name,
            discovery_info.host,
            discovery_info.port,
            discovery_info.properties,
        )

        if ZEROCONF_TYPE_LINKPLAY not in discovery_info.type:
            LOGGER.debug(
                "Ignoring Zeroconf discovery for type: %s (expected %s)",
                discovery_info.type,
                ZEROCONF_TYPE_LINKPLAY,
            )
            return self.async_abort(reason="not_supported")

        host = discovery_info.host
        udn_from_txt = discovery_info.properties.get("uuid")
        if udn_from_txt:
            await self.async_set_unique_id(udn_from_txt)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        try:
            # If Zeroconf TXT records provide a direct path to description.xml, construct location.
            constructed_location = f"http://{host}:49152/description.xml"
            LOGGER.info(
                "Zeroconf for host %s. Attempting validation (UPnP location may not be derived from this step directly)",
                host,
            )
            device_info = await _validate_device_and_get_info(
                self.hass, host, location=constructed_location
            )

        except CannotConnect:
            try:
                device_info = await _validate_device_and_get_info(
                    self.hass, host, location=None
                )
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")
        except (OSError, ValueError) as err:
            LOGGER.error(
                "Unexpected error during Zeroconf validation for %s: %s",
                host,
                err,
            )
            return self.async_abort(reason="unknown")

        # If UDN wasn't in TXT, it's now in device_info from HTTP validation
        await self.async_set_unique_id(device_info.udn)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: device_info.host,
                CONF_UPNP_LOCATION: device_info.location,
            }
        )

        self._discovered_info = device_info
        self.context["title_placeholders"] = {"name": device_info.name}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation of discovered device."""
        if user_input is not None and self._discovered_info is not None:
            entry_data = {
                CONF_HOST: self._discovered_info.host,
                CONF_UDN: self._discovered_info.udn,
                CONF_UPNP_LOCATION: self._discovered_info.location,
            }
            return self.async_create_entry(title=self._discovered_info.name, data=entry_data)

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": (
                    self._discovered_info.name
                    if self._discovered_info is not None
                    else "Discovered WiiM Device"
                )
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
