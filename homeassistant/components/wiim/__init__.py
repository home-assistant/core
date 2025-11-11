# homeassistant/components/wiim/__init__.py
"""The WiiM integration."""

from __future__ import annotations

import socket
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientSession, TCPConnector
from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.client import UpnpDevice
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpConnectionError, UpnpError
import voluptuous as vol
from wiim.consts import (
    MANUFACTURER_WIIM,
    UPNP_DEVICE_TYPE as SDK_UPNP_ST_MEDIA_RENDERER,
)
from wiim.controller import WiimController
from wiim.endpoint import WiimApiEndpoint
from wiim.exceptions import WiimDeviceException, WiimRequestException
from wiim.wiim_device import WiimDevice

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .config_flow import CannotConnect, NotWiimDevice, _validate_device_and_get_info
from .const import (
    CONF_DEVICES,
    CONF_NAME,
    CONF_UDN,
    CONF_UPNP_LOCATION,
    DEFAULT_AVAILABILITY_POLLING_INTERVAL,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    PLATFORMS,
    SDK_LOGGER,
    WiimData,
)

type WiimConfigEntry = ConfigEntry

# Schema for individual devices in YAML
DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    }
)

# Schema for the wiim domain in configuration.yaml
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the WiiM component."""
    # Ensure hass.data[DOMAIN] is initialized with the WiimData object
    if DOMAIN not in hass.data:
        session = async_get_clientsession(hass)
        wiim_controller = WiimController(session, event_callback=None)
        hass.data[DOMAIN] = WiimData(
            controller=wiim_controller,
            entity_id_to_udn_map={},
            entities_by_entity_id={},
        )
        SDK_LOGGER.debug(
            "Initialized hass.data[%s] with WiimData and controller.", DOMAIN
        )

    if config.get(DOMAIN):
        if isinstance(config[DOMAIN], dict):
            yaml_config = config[DOMAIN]
            devices_config = yaml_config.get(CONF_DEVICES, [])

            if devices_config:
                SDK_LOGGER.debug(
                    "Async_setup for WiiM integration with YAML config: %s",
                    config.get(DOMAIN),
                )

                for device_conf in devices_config:
                    host = device_conf.get(CONF_HOST)
                    if not host:
                        SDK_LOGGER.warning(
                            "YAML device configuration missing 'host'. Skipping entry: %s",
                            device_conf,
                        )
                        continue

                    constructed_location = f"http://{host}:49152/description.xml"

                    async def _import_device_from_yaml(
                        host_to_import: str,
                        location_to_import: str,
                        raw_device_conf: dict[str, Any],
                    ):
                        """Helper to handle single device import asynchronously."""
                        try:
                            device_info = await _validate_device_and_get_info(
                                hass, host_to_import, location=location_to_import
                            )
                            udn = device_info[CONF_UDN]
                            name = device_info[CONF_NAME]
                            upnp_location_yaml = device_info.get(CONF_UPNP_LOCATION)

                            entries = hass.config_entries.async_entries(DOMAIN)
                            existing_entry = next(
                                (entry for entry in entries if entry.unique_id == udn),
                                None,
                            )
                            if existing_entry:
                                SDK_LOGGER.info(
                                    "Config entry for WiiM device %s (UDN: %s) already exists. YAML entry for host %s will be ignored.",
                                    existing_entry.title,
                                    udn,
                                    host_to_import,
                                )
                                # Optional: update existing entry if host changed in YAML
                                # if existing_entry.data.get(CONF_HOST) != host_to_import:
                                #     hass.config_entries.async_update_entry(
                                #         existing_entry, data={**existing_entry.data, CONF_HOST: host_to_import}
                                #     )
                                return

                            SDK_LOGGER.info(
                                "Creating new config entry for WiiM device %s (UDN: %s) from YAML.",
                                name,
                                udn,
                            )
                            await hass.config_entries.flow.async_init(
                                DOMAIN,
                                context={"source": SOURCE_IMPORT},
                                data={
                                    CONF_HOST: host_to_import,
                                    CONF_UDN: udn,
                                    CONF_NAME: name,
                                    CONF_UPNP_LOCATION: upnp_location_yaml,
                                },
                            )
                        except CannotConnect:
                            SDK_LOGGER.warning(
                                "Cannot connect to WiiM device %s specified in YAML. Skipping.",
                                host_to_import,
                            )
                        except NotWiimDevice:
                            SDK_LOGGER.warning(
                                "Device %s from YAML is not a WiiM device. Skipping.",
                                host_to_import,
                            )
                        except Exception as e:
                            SDK_LOGGER.exception(
                                "Error processing YAML device %s: %s", host_to_import, e
                            )
                            raise

                    hass.async_create_task(
                        _import_device_from_yaml(
                            host, constructed_location, device_conf
                        )
                    )
            else:
                SDK_LOGGER.debug(
                    "YAML configuration for WiiM integration found but 'devices' list is empty."
                )
        else:
            SDK_LOGGER.warning(
                "YAML configuration for WiiM integration is not a dictionary. Skipping import."
            )
    else:
        SDK_LOGGER.debug(
            "No 'wiim' domain found in YAML configuration. Relying on UI configuration."
        )

    return True


def _get_local_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


class MinimalUpnpShell(UpnpDevice):
    """Minimal mock implementation of a UPnP device for WiiM integration."""

    def __init__(self, _udn, _host, _name, _requester):
        """Initialize the MinimalUpnpShell.
        # pylint: disable=super-init-not-called

        Args:
            _udn (str): Unique Device Name (UDN).
            _host (str): IP address of the device.
            _name (str): Friendly name of the device.
            _requester (AiohttpRequester): HTTP requester used for UPnP communication.
        """
        self.udn = _udn
        self.friendly_name = _name or DEFAULT_DEVICE_NAME
        self.manufacturer = MANUFACTURER_WIIM
        self.model_name = "WiiM Device"
        self.device_type = SDK_UPNP_ST_MEDIA_RENDERER
        self.device_url = f"http://{_host}:49152/description.xml"
        self.presentation_url = f"http://{_host}"
        self._services = {}
        self.requester = _requester
        self.client = None
        self.available = True

    def service(self, service_type):
        """Return the UPnP service by service ID, if available."""
        return self._services.get(service_type)

    def add_service(self, service):
        """Add a UPnP service to the internal service registry."""
        self._services[service.service_id] = service


async def async_setup_entry(hass: HomeAssistant, entry: WiimConfigEntry) -> bool:
    """Set up WiiM from a config entry (called after async_setup or UI flow)."""
    SDK_LOGGER.debug(
        "Setting up WiiM entry: %s (UDN: %s, Source: %s)",
        entry.title,
        entry.data.get(CONF_UDN),
        entry.source,
    )

    # Ensure domain data is initialized (could be set by async_setup or another entry)
    if DOMAIN not in hass.data:
        session = async_get_clientsession(hass)
        wiim_controller = WiimController(session, event_callback=None)
        hass.data[DOMAIN] = WiimData(
            controller=wiim_controller,
            entity_id_to_udn_map={},
            entities_by_entity_id={},
        )

    wiim_domain_data = hass.data[DOMAIN]
    controller = wiim_domain_data.controller
    controller.session = async_get_clientsession(hass)

    host = entry.data[CONF_HOST]
    udn = entry.data[CONF_UDN]
    upnp_location = entry.data.get(CONF_UPNP_LOCATION)

    session = async_get_clientsession(hass)
    requester = AiohttpRequester(timeout=10)
    upnp_device_instance: UpnpDevice | None = None
    wiim_device_sdk: WiimDevice | None = None

    if upnp_location and host:
        upnp_location = upnp_location.replace(urlparse(upnp_location).hostname, host)

    try:
        if upnp_location:
            SDK_LOGGER.debug(
                "Attempting to create UpnpDevice for %s from location: %s",
                entry.title,
                upnp_location,
            )
            try:
                factory = UpnpFactory(requester)
                upnp_device_instance = await factory.async_create_device(upnp_location)
                SDK_LOGGER.debug(
                    "Successfully created UpnpDevice: %s",
                    upnp_device_instance.friendly_name,
                )
            except (TimeoutError, UpnpConnectionError, UpnpError) as err:
                SDK_LOGGER.warning(
                    "Failed to create UpnpDevice from location %s for %s: %s",
                    upnp_location,
                    entry.title,
                    err,
                )
                raise ConfigEntryNotReady(
                    f"Failed to connect to UPnP device at {upnp_location}: {err}"
                ) from err
        else:
            SDK_LOGGER.warning(
                "UPnP location not found in config entry for %s (UDN: %s, Host: %s). "
                "WiiM device will attempt to initialize; UPnP eventing might be unavailable or delayed.",
                entry.title,
                udn,
                host,
            )

            upnp_device_instance = MinimalUpnpShell(udn, host, entry.title, requester)

        sessions = ClientSession(connector=TCPConnector(ssl=False))
        http_api = WiimApiEndpoint(
            protocol="https", port=443, endpoint=host, session=sessions
        )
        ha_host_ip = None

        if hass.config.internal_url:
            if isinstance(hass.config.internal_url, str) and hass.config.internal_url:
                try:
                    parsed_url = urlparse(hass.config.internal_url)
                    if parsed_url.hostname:
                        ha_host_ip = parsed_url.hostname
                        SDK_LOGGER.debug(
                            "Using internal_url hostname as HA host IP: %s", ha_host_ip
                        )
                except ValueError:
                    SDK_LOGGER.warning(
                        "Invalid internal_url configured: %s", hass.config.internal_url
                    )
        elif hass.config.external_url:
            if isinstance(hass.config.external_url, str) and hass.config.external_url:
                try:
                    parsed_url = urlparse(hass.config.external_url)
                    if parsed_url.hostname:
                        ha_host_ip = parsed_url.hostname
                        SDK_LOGGER.debug(
                            "Using external_url hostname as HA host IP: %s", ha_host_ip
                        )
                except ValueError:
                    SDK_LOGGER.warning(
                        "Invalid external_url configured: %s", hass.config.external_url
                    )

        if not ha_host_ip:
            ha_host_ip = await hass.async_add_executor_job(_get_local_ip)
            if ha_host_ip:
                SDK_LOGGER.debug(
                    "Using socket fallback to determine HA host IP: %s", ha_host_ip
                )
            else:
                SDK_LOGGER.error(
                    "Failed to determine Home Assistant host IP using socket fallback"
                )

        wiim_device_sdk = WiimDevice(
            upnp_device=upnp_device_instance,
            session=session,
            http_api_endpoint=http_api,
            ha_host_ip=ha_host_ip,
            polling_interval=DEFAULT_AVAILABILITY_POLLING_INTERVAL,
        )

        await controller.add_device(wiim_device_sdk)

        entry.runtime_data = wiim_device_sdk
        SDK_LOGGER.info(
            "WiiM device %s (UDN: %s) linked to HASS. Name: '%s', HTTP: %s, UPnP Location: %s",
            entry.entry_id,
            wiim_device_sdk.udn,
            wiim_device_sdk.name,
            host,
            upnp_location or "N/A",
        )

    except ConfigEntryNotReady:
        if wiim_device_sdk:
            await wiim_device_sdk.disconnect()
        raise
    except WiimRequestException as err:
        if wiim_device_sdk:
            await wiim_device_sdk.disconnect()
        SDK_LOGGER.error("HTTP API request failed during setup for %s: %s", host, err)
        raise ConfigEntryNotReady(f"HTTP API request failed for {host}: {err}") from err
    except WiimDeviceException as err:
        if wiim_device_sdk:
            await wiim_device_sdk.disconnect()
        SDK_LOGGER.error("SDK Device Exception during setup for %s: %s", host, err)
        raise ConfigEntryNotReady(f"SDK Device error for {host}: {err}") from err
    except Exception as err:
        if wiim_device_sdk:
            await wiim_device_sdk.disconnect()
        SDK_LOGGER.exception(
            "Unexpected error setting up WiiM device %s: %s", host, err
        )
        raise ConfigEntryNotReady(f"Unexpected error for {host}: {err}") from err

    async def _async_shutdown_event_handler(event: Event) -> None:
        SDK_LOGGER.info(
            "Home Assistant stopping, disconnecting WiiM device: %s",
            wiim_device_sdk.name,
        )
        await wiim_device_sdk.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _async_shutdown_event_handler
        )
    )

    # entry.async_on_unload(wiim_device_sdk.disconnect)
    # Unload function to remove from controller and disconnect
    async def _unload_entry_cleanup():
        SDK_LOGGER.debug("Running unload cleanup for %s", wiim_device_sdk.name)
        await controller.remove_device(wiim_device_sdk.udn)
        await wiim_device_sdk.disconnect()

    entry.async_on_unload(_unload_entry_cleanup)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WiimConfigEntry) -> bool:
    """Unload a config entry."""
    SDK_LOGGER.info(
        "Unloading WiiM entry: %s (UDN: %s)", entry.title, entry.data.get(CONF_UDN)
    )

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        wiim_domain_data = hass.data.get(DOMAIN)
        if wiim_domain_data:
            udn_to_remove = entry.data.get(CONF_UDN)
            if udn_to_remove:
                keys_to_del = [
                    entity_id
                    for entity_id, udn in wiim_domain_data.entity_id_to_udn_map.items()
                    if udn == udn_to_remove
                ]
                for key in keys_to_del:
                    del wiim_domain_data.entity_id_to_udn_map[key]
                    SDK_LOGGER.debug(
                        "Removed %s from entity_id_to_udn_map during unload.", key
                    )

        remaining_entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id
        ]
        if not remaining_entries:
            hass.data.pop(DOMAIN, None)
            SDK_LOGGER.info("Last WiiM entry unloaded, cleaning up domain data.")
    return unload_ok
