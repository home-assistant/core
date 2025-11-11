# homeassistant/components/wiim/config_flow.py
"""Config flow for WiiM integration."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.client import UpnpDevice
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpConnectionError, UpnpError
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_UDN,
    CONF_UPNP_LOCATION,
    DOMAIN,
    SDK_LOGGER,
    ZEROCONF_TYPE_LINKPLAY,
    WiimData,
)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

COMMON_UPNP_HTTP_PORTS = [80, 49152, 1400]


async def _validate_device_and_get_info(
    hass: HomeAssistant, host_or_udn: str, location: str | None = None
) -> dict[str, Any]:
    """Validate the given host or UDN can be reached and is a WiiM device.

    If location is provided, uses that directly for UPnP device creation.
    Otherwise, assumes host_or_udn is an IP and tries to discover UPnP info.
    Returns device info (UDN, name, model, host, location).
    """
    # session = async_get_clientsession(hass)
    requester = AiohttpRequester(timeout=10)
    upnp_device: UpnpDevice | None = None
    actual_host = host_or_udn
    device_info_from_http: dict[str, Any] | None = None

    try:
        if location:
            SDK_LOGGER.debug("Validating UPnP device at location: %s", location)
            # upnp_device = await UpnpDevice.async_create_device(requester, location)
            factory = UpnpFactory(requester)
            upnp_device = await factory.async_create_device(location)
            actual_host = urlparse(location).hostname or actual_host
        elif "uuid:" in host_or_udn.lower():
            raise CannotConnect(
                f"Validation by UDN ({host_or_udn}) alone is not supported for connection. Use IP/host or discovery."
            )
        else:
            SDK_LOGGER.debug(
                "No UPnP location provided for %s, attempting HTTP validation.",
                actual_host,
            )
            # session = ClientSession(connector=TCPConnector(ssl=False))
            # temp_http_api = WiimApiEndpoint(
            #     protocol="https", port=443, endpoint=actual_host, session=session
            # )
            # try:
            #     status = await temp_http_api.json_request(WiimHttpCommand.DEVICE_STATUS)
            #     await session.close()
            #     udn = status.get(SDKDeviceAttribute.UUID)
            #     name = status.get(SDKDeviceAttribute.DEVICE_NAME, DEFAULT_DEVICE_NAME)
            #     if not udn:
            #         raise CannotConnect(
            #             f"Could not retrieve UDN from {actual_host} via HTTP. Response: {status}"
            #         )
            #     device_info_from_http = {
            #         CONF_UDN: udn,
            #         CONF_NAME: name,
            #         "model": status.get(SDKDeviceAttribute.PROJECT, "WiiM Device"),
            #         CONF_HOST: actual_host,
            #         CONF_UPNP_LOCATION: None,
            #     }
            #     SDK_LOGGER.info(
            #         "HTTP validation successful for %s: UDN %s", actual_host, udn
            #     )
            # except Exception as e:
            #     SDK_LOGGER.error(
            #         "Error validating host %s via HTTP: %s", actual_host, e
            #     )
            #     await session.close()
            #     raise CannotConnect(
            #         f"Failed to connect or get info from {actual_host} via HTTP: {e}"
            #     ) from e

        if upnp_device:
            return {
                CONF_UDN: upnp_device.udn,
                CONF_NAME: upnp_device.friendly_name,
                "model": upnp_device.model_name or "WiiM Device",
                CONF_HOST: actual_host,
                CONF_UPNP_LOCATION: location or upnp_device.device_url,
            }
        if device_info_from_http:
            return device_info_from_http
        raise CannotConnect("Could not determine device information via UPnP or HTTP.")
    except UpnpConnectionError as err:
        SDK_LOGGER.warning(
            "Connection error while validating WiiM device at %s: %s",
            actual_host or location,
            err,
        )
        raise CannotConnect(f"Failed to connect to UPnP device: {err}") from err
    except UpnpError as err:
        SDK_LOGGER.warning(
            "UPnP library error while validating WiiM device at %s: %s",
            actual_host or location,
            err,
        )
        raise CannotConnect(f"UPnP library error: {err}") from err
    except TimeoutError as err:
        SDK_LOGGER.warning(
            "Timeout while validating Wiiim device at %s: %s",
            actual_host or location,
            err,
        )
        raise CannotConnect(f"Timeout connecting to device: {err}") from err


class WiimConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiiM."""

    VERSION = 1
    _discovered_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step when user adds integration manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                constructed_location = f"http://{host}:49152/description.xml"
                device_info = await _validate_device_and_get_info(
                    self.hass, host, location=constructed_location
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except NotWiimDevice:
                errors["base"] = "not_wiim_device"
            except Exception as e:
                SDK_LOGGER.exception(
                    "Unexpected exception during user step validation for host %s: %s",
                    host,
                    e,
                )
                errors["base"] = "unknown"
                raise
            else:
                await self.async_set_unique_id(device_info[CONF_UDN])
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: device_info[CONF_HOST],
                        CONF_UPNP_LOCATION: device_info.get(CONF_UPNP_LOCATION),
                    }
                )
                entry_data = {
                    CONF_HOST: device_info[CONF_HOST],
                    CONF_UDN: device_info[CONF_UDN],
                    CONF_UPNP_LOCATION: device_info.get(CONF_UPNP_LOCATION),
                }
                return self.async_create_entry(
                    title=device_info[CONF_NAME], data=entry_data
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        SDK_LOGGER.debug("Handling import step with config: %s", import_config)

        host = import_config.get(CONF_HOST)
        udn = import_config.get(CONF_UDN)
        name = import_config.get(CONF_NAME, f"WiiM Device ({host or udn})")
        upnp_location = import_config.get(CONF_UPNP_LOCATION)

        if not udn:
            SDK_LOGGER.warning(
                "UDN missing in imported config for host %s. Cannot create unique entry.",
                host,
            )
            return self.async_abort(reason="invalid_import_data")

        await self.async_set_unique_id(udn)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: host,
                CONF_UDN: udn,
                CONF_NAME: name,
                CONF_UPNP_LOCATION: upnp_location,
            },
        )

    # async def async_step_ssdp(
    #     self, discovery_info: ssdp.SsdpServiceInfo
    # ) -> ConfigFlowResult:
    #     """Handle UPnP discovery via SSDP."""
    #     SDK_LOGGER.debug("SSDP discovery received: %s", discovery_info.upnp) # Log relevant parts

    #     # Ensure it's a MediaRenderer device type, or other known WiiM types
    #     # (UPNP_ST_MEDIA_RENDERER is already defined in const.py)
    #     if UPNP_ST_MEDIA_RENDERER not in discovery_info.ssdp_st: # Check if ST is a set or string
    #         SDK_LOGGER.debug("Ignoring SSDP discovery for type: %s", discovery_info.ssdp_st)
    #         return self.async_abort(reason="not_supported_device")

    #     location = discovery_info.ssdp_location
    #     if not location:
    #         SDK_LOGGER.warning("SSDP discovery missing location. USN: %s", discovery_info.ssdp_usn)
    #         return self.async_abort(reason="cannot_connect") # Or "missing_location"

    #     # Host for logging, UDN for unique_id
    #     host = urlparse(location).hostname or "Unknown host"

    #     try:
    #         # _validate_device_and_get_info uses the location to create UpnpDevice
    #         device_info = await _validate_device_and_get_info(self.hass, host, location=location)
    #     except CannotConnect:
    #         return self.async_abort(reason="cannot_connect")
    #     except NotWiimDevice:
    #         return self.async_abort(reason="not_wiim_device")
    #     except Exception as e: # Catch any other unexpected error during validation
    #         SDK_LOGGER.error("Unexpected error during SSDP validation for %s: %s", location, e, exc_info=True)
    #         return self.async_abort(reason="unknown")

    #     await self.async_set_unique_id(device_info[CONF_UDN])
    #     self._abort_if_unique_id_configured(
    #         updates={
    #             CONF_HOST: device_info[CONF_HOST],
    #             CONF_UPNP_LOCATION: device_info.get(CONF_UPNP_LOCATION) # Ensure location is passed for update
    #         }
    #     )

    #     self._discovered_info = device_info # Store for confirmation step
    #     self.context["title_placeholders"] = {"name": device_info[CONF_NAME]}
    #     return await self.async_step_discovery_confirm()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""
        SDK_LOGGER.debug(
            "Zeroconf discovery received: Name: %s, Host: %s, Port: %s, Properties: %s",
            discovery_info.name,
            discovery_info.host,
            discovery_info.port,
            discovery_info.properties,
        )

        if ZEROCONF_TYPE_LINKPLAY not in discovery_info.type:
            SDK_LOGGER.debug(
                "Ignoring Zeroconf discovery for type: %s (expected %s)",
                discovery_info.type,
                ZEROCONF_TYPE_LINKPLAY,
            )
            return self.async_abort(reason="not_supported_device")

        host = discovery_info.host
        udn_from_txt = discovery_info.properties.get("uuid")
        if udn_from_txt:
            await self.async_set_unique_id(udn_from_txt)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        try:
            # If Zeroconf TXT records provide a direct path to description.xml, construct location.
            constructed_location = f"http://{host}:49152/description.xml"
            SDK_LOGGER.info(
                "Zeroconf for host %s. Attempting validation (UPnP location may not be derived from this step directly).",
                host,
            )
            device_info = await _validate_device_and_get_info(
                self.hass, host, location=constructed_location
            )

            wiim_data: WiimData | None = self.hass.data.get(DOMAIN)
            if wiim_data and wiim_data.controller:
                wiim_device_sdk = wiim_data.controller.get_device(udn_from_txt)
                if wiim_device_sdk and not wiim_device_sdk.available:
                    if not await wiim_device_sdk.async_init_services_and_subscribe():
                        SDK_LOGGER.warning(
                            "Device %s initialized with potentially limited UPnP functionality (location was: %s). HTTP API might be primary.",
                            udn_from_txt,
                            constructed_location or "Unknown",
                        )

        except CannotConnect:
            try:
                device_info = await _validate_device_and_get_info(
                    self.hass, host, location=None
                )
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")
            except NotWiimDevice:
                return self.async_abort(reason="not_wiim_device")
        except NotWiimDevice:
            return self.async_abort(reason="not_wiim_device")
        except Exception as e:
            SDK_LOGGER.error(
                "Unexpected error during Zeroconf validation for %s: %s",
                host,
                e,
                exc_info=True,
            )
            raise
            # return self.async_abort(reason="unknown")

        # If UDN wasn't in TXT, it's now in device_info from HTTP validation
        await self.async_set_unique_id(device_info[CONF_UDN])
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: device_info[CONF_HOST],
                CONF_UPNP_LOCATION: device_info.get(CONF_UPNP_LOCATION),
            }
        )

        self._discovered_info = device_info
        self.context["title_placeholders"] = {"name": device_info[CONF_NAME]}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation of discovered device."""
        if user_input is not None:
            entry_data = {
                CONF_HOST: self._discovered_info[CONF_HOST],
                CONF_UDN: self._discovered_info[CONF_UDN],
                CONF_UPNP_LOCATION: self._discovered_info.get(CONF_UPNP_LOCATION),
            }
            return self.async_create_entry(
                title=self._discovered_info[CONF_NAME], data=entry_data
            )

        # self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self._discovered_info.get(CONF_NAME, "Discovered WiiM Device")
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class NotWiimDevice(HomeAssistantError):
    """Error to indicate the device is not a WiiM device."""
