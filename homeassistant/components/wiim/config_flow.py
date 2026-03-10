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

from .const import CONF_UDN, CONF_UPNP_LOCATION, DOMAIN, LOGGER, UPNP_PORT

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def _validate_device_and_get_info(
    hass: HomeAssistant, host_or_udn: str, location: str | None = None
) -> WiimProbeResult:
    """Validate the given host or UDN can be reached and is a WiiM device."""
    session = async_get_clientsession(hass)

    if location is not None:
        LOGGER.debug("Validating UPnP device at location: %s", location)
        try:
            probe_result = await async_probe_wiim_device(
                location,
                session,
                host=host_or_udn,
            )
        except TimeoutError as err:
            LOGGER.warning(
                "Timeout while validating WiiM device at %s: %s",
                location,
                err,
            )
            raise CannotConnect(f"Timeout connecting to device: {err}") from err

        if probe_result is None:
            raise CannotConnect("Could not determine device information via UPnP.")
        return probe_result

    is_udn = "uuid:" in host_or_udn.lower()
    LOGGER.debug(
        "No UPnP location provided for %s, validation cannot continue",
        host_or_udn,
    )
    if is_udn:
        raise CannotConnect(
            f"Validation by UDN ({host_or_udn}) alone is not supported for connection. Use IP/host or discovery."
        )

    raise CannotConnect("Could not determine device information via UPnP.")


class WiimConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiiM."""

    _discovered_info: WiimProbeResult

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step when user adds integration manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                device_info = await _validate_device_and_get_info(
                    self.hass,
                    host,
                    location=f"http://{host}:{UPNP_PORT}/description.xml",
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(device_info.udn)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: device_info.host,
                        CONF_UPNP_LOCATION: device_info.location,
                    }
                )
                return self.async_create_entry(
                    title=device_info.name,
                    data={
                        CONF_HOST: device_info.host,
                        CONF_UDN: device_info.udn,
                        CONF_UPNP_LOCATION: device_info.location,
                    },
                )

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

        host = discovery_info.host
        udn_from_txt = discovery_info.properties.get("uuid")
        if udn_from_txt:
            await self.async_set_unique_id(udn_from_txt)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        try:
            device_info = await _validate_device_and_get_info(
                self.hass,
                host,
                location=f"http://{host}:{UPNP_PORT}/description.xml",
            )
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

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
        discovered_info = getattr(self, "_discovered_info", None)
        if user_input is not None and discovered_info is not None:
            return self.async_create_entry(
                title=discovered_info.name,
                data={
                    CONF_HOST: discovered_info.host,
                    CONF_UDN: discovered_info.udn,
                    CONF_UPNP_LOCATION: discovered_info.location,
                },
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": (
                    discovered_info.name
                    if discovered_info is not None
                    else "Discovered WiiM Device"
                )
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
