"""Open ports in your router for Home Assistant and provide statistics."""
import asyncio
from ipaddress import ip_address
from operator import itemgetter

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import get_local_ip

from .const import (
    CONF_LOCAL_IP,
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DISCOVERY_LOCATION,
    DISCOVERY_ST,
    DISCOVERY_UDN,
    DISCOVERY_USN,
    DOMAIN,
    DOMAIN_CONFIG,
    DOMAIN_COORDINATORS,
    DOMAIN_DEVICES,
    DOMAIN_LOCAL_IP,
    LOGGER as _LOGGER,
)
from .device import Device

NOTIFICATION_ID = "upnp_notification"
NOTIFICATION_TITLE = "UPnP/IGD Setup"

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Optional(CONF_LOCAL_IP): vol.All(ip_address, cv.string)})},
    extra=vol.ALLOW_EXTRA,
)


async def async_discover_and_construct(
    hass: HomeAssistantType, udn: str = None, st: str = None
) -> Device:
    """Discovery devices and construct a Device for one."""
    # pylint: disable=invalid-name
    discovery_infos = await Device.async_discover(hass)
    _LOGGER.debug("Discovered devices: %s", discovery_infos)
    if not discovery_infos:
        _LOGGER.info("No UPnP/IGD devices discovered")
        return None

    if udn:
        # Get the discovery info with specified UDN/ST.
        filtered = [di for di in discovery_infos if di[DISCOVERY_UDN] == udn]
        if st:
            filtered = [di for di in discovery_infos if di[DISCOVERY_ST] == st]
        if not filtered:
            _LOGGER.warning(
                'Wanted UPnP/IGD device with UDN "%s" not found, aborting', udn
            )
            return None

        # Ensure we're always taking the latest, if we filtered only on UDN.
        filtered = sorted(filtered, key=itemgetter(DISCOVERY_ST), reverse=True)
        discovery_info = filtered[0]
    else:
        # Get the first/any.
        discovery_info = discovery_infos[0]
        if len(discovery_infos) > 1:
            device_name = discovery_info.get(
                DISCOVERY_USN, discovery_info.get(DISCOVERY_LOCATION, "")
            )
            _LOGGER.info("Detected multiple UPnP/IGD devices, using: %s", device_name)

    location = discovery_info[DISCOVERY_LOCATION]
    return await Device.async_create_device(hass, location)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up UPnP component."""
    _LOGGER.debug("async_setup, config: %s", config)
    conf_default = CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]
    conf = config.get(DOMAIN, conf_default)
    local_ip = await hass.async_add_executor_job(get_local_ip)
    hass.data[DOMAIN] = {
        DOMAIN_CONFIG: conf,
        DOMAIN_COORDINATORS: {},
        DOMAIN_DEVICES: {},
        DOMAIN_LOCAL_IP: conf.get(CONF_LOCAL_IP, local_ip),
    }

    # Only start if set up via configuration.yaml.
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """Set up UPnP/IGD device from a config entry."""
    _LOGGER.debug("async_setup_entry, config_entry: %s", config_entry.data)

    # discover and construct
    udn = config_entry.data.get(CONFIG_ENTRY_UDN)
    st = config_entry.data.get(CONFIG_ENTRY_ST)  # pylint: disable=invalid-name
    try:
        device = await async_discover_and_construct(hass, udn, st)
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady from err

    if not device:
        _LOGGER.info("Unable to create UPnP/IGD, aborting")
        raise ConfigEntryNotReady

    # Save device
    hass.data[DOMAIN][DOMAIN_DEVICES][device.udn] = device

    # Ensure entry has proper unique_id.
    if config_entry.unique_id != device.unique_id:
        hass.config_entries.async_update_entry(
            entry=config_entry,
            unique_id=device.unique_id,
        )

    # Create device registry entry.
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_UPNP, device.udn)},
        identifiers={(DOMAIN, device.udn)},
        name=device.name,
        manufacturer=device.manufacturer,
        model=device.model_name,
    )

    # Create sensors.
    _LOGGER.debug("Enabling sensors")
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    return True


async def async_unload_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> bool:
    """Unload a UPnP/IGD device from a config entry."""
    udn = config_entry.data.get(CONFIG_ENTRY_UDN)
    if udn in hass.data[DOMAIN][DOMAIN_DEVICES]:
        del hass.data[DOMAIN][DOMAIN_DEVICES][udn]
    if udn in hass.data[DOMAIN][DOMAIN_COORDINATORS]:
        del hass.data[DOMAIN][DOMAIN_COORDINATORS][udn]

    _LOGGER.debug("Deleting sensors")
    return await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
