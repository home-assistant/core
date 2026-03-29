"""Home Assistant integration for OPNsense firewalls.

This integration provides monitoring and control of OPNsense firewall devices,
including system information, network interfaces, firewall rules, DHCP leases,
and various other OPNsense features through the Home Assistant interface.
"""

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

import aiohttp
from aiopnsense import OPNsenseClient
import awesomeversion
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEVICE_TRACKER_ENABLED,
    CONF_DEVICE_TRACKER_SCAN_INTERVAL,
    CONF_DEVICE_UNIQUE_ID,
    CONF_DEVICES,
    CONF_GRANULAR_SYNC_OPTIONS,
    CONF_SYNC_CARP,
    CONF_SYNC_CERTIFICATES,
    CONF_SYNC_DHCP_LEASES,
    CONF_SYNC_FIREWALL_AND_NAT,
    CONF_SYNC_FIRMWARE_UPDATES,
    CONF_SYNC_GATEWAYS,
    CONF_SYNC_INTERFACES,
    CONF_SYNC_NOTICES,
    CONF_SYNC_SERVICES,
    CONF_SYNC_SPEEDTEST,
    CONF_SYNC_TELEMETRY,
    CONF_SYNC_UNBOUND,
    CONF_SYNC_VNSTAT,
    CONF_SYNC_VPN,
    DEFAULT_DEVICE_TRACKER_ENABLED,
    DEFAULT_DEVICE_TRACKER_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SYNC_OPTION_VALUE,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    GRANULAR_SYNC_PREFIX,
    LOADED_PLATFORMS,
    OPNSENSE_CLIENT,
    OPNSENSE_MIN_FIRMWARE,
    PLATFORMS,
    SHOULD_RELOAD,
    VERSION,
)
from .coordinator import OPNsenseDataUpdateCoordinator
from .helpers import is_private_ip
from .models import OPNsenseData

_LOGGER: logging.Logger = logging.getLogger(__name__)

CONF_API_KEY = "api_key"
CONF_API_SECRET = "api_secret"
CONF_TRACKER_INTERFACES = "tracker_interfaces"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_API_SECRET): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                vol.Optional(CONF_TRACKER_INTERFACES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update for the OPNsense integration.

    This function is called when the configuration entry options are updated.
    It handles reloading the integration if necessary, removing entities that
    are no longer enabled based on granular sync options, and cleaning up
    device tracker devices if device tracking is disabled.

    Parameters
    ----------
    hass : HomeAssistant
        The Home Assistant instance.
    entry : ConfigEntry
        The configuration entry for the OPNsense integration.

    """
    if getattr(entry.runtime_data, SHOULD_RELOAD, True):
        _LOGGER.info("[async_update_listener] Reloading")

        uid_prefix = entry.unique_id
        removal_prefixes: list[str] = []
        for item, prefix in GRANULAR_SYNC_PREFIX.items():
            if not entry.data.get(item, DEFAULT_SYNC_OPTION_VALUE):
                removal_prefixes.extend(prefix)
        _LOGGER.debug("[async_update_listener] removal_prefixes: %s", removal_prefixes)

        entity_registry = er.async_get(hass)
        for ent in er.async_entries_for_config_entry(
            registry=entity_registry, config_entry_id=entry.entry_id
        ):
            for pre in removal_prefixes:
                if ent.unique_id.startswith(f"{uid_prefix}_{pre}"):
                    _LOGGER.debug(
                        "[async_update_listener] removing entity_id: %s, unique_id: %s",
                        ent.entity_id,
                        ent.unique_id,
                    )
                    entity_registry.async_remove(ent.entity_id)
                    break
        dt_enabled = entry.options.get(
            CONF_DEVICE_TRACKER_ENABLED, DEFAULT_DEVICE_TRACKER_ENABLED
        )
        if not dt_enabled:
            device_registry = dr.async_get(hass)
            devices = dr.async_entries_for_config_entry(
                registry=device_registry, config_entry_id=entry.entry_id
            )
            for device in devices:
                if device.via_device_id:
                    _LOGGER.debug(
                        "[async_update_listener] removing device: %s", device.name
                    )
                    device_registry.async_remove_device(device.id)
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
    else:
        _LOGGER.info("[async_update_listener] Not Reloading")
        setattr(entry.runtime_data, SHOULD_RELOAD, True)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OPNsense integration at the domain level.

    This function is called during Home Assistant startup to initialize
    integration-level services for the OPNsense domain.

    Parameters
    ----------
    hass : HomeAssistant
        The Home Assistant instance.
    config : ConfigType
        The configuration dictionary (unused for config entry only integrations).

    Returns:
    -------
    bool
        Always returns True to indicate successful setup.

    """
    if DOMAIN in config:
        legacy_config = config[DOMAIN]
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data={
                    CONF_NAME: "OPNsense",
                    CONF_URL: legacy_config[CONF_URL],
                    CONF_USERNAME: legacy_config[CONF_API_KEY],
                    CONF_PASSWORD: legacy_config[CONF_API_SECRET],
                    CONF_VERIFY_SSL: legacy_config.get(CONF_VERIFY_SSL, False),
                    CONF_GRANULAR_SYNC_OPTIONS: True,
                    CONF_SYNC_TELEMETRY: True,
                    CONF_SYNC_INTERFACES: False,
                    CONF_SYNC_DHCP_LEASES: False,
                    CONF_SYNC_GATEWAYS: False,
                    CONF_SYNC_FIREWALL_AND_NAT: False,
                    CONF_SYNC_NOTICES: False,
                    CONF_SYNC_FIRMWARE_UPDATES: False,
                    CONF_SYNC_CARP: False,
                    CONF_SYNC_SERVICES: False,
                    CONF_SYNC_VPN: False,
                    CONF_SYNC_CERTIFICATES: False,
                    CONF_SYNC_UNBOUND: False,
                    CONF_SYNC_VNSTAT: False,
                    CONF_SYNC_SPEEDTEST: False,
                    "_import_options": {
                        CONF_DEVICE_TRACKER_ENABLED: True,
                        CONF_DEVICES: [],
                    },
                },
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the OPNsense integration from a configuration entry.

    This function initializes the OPNsense client, coordinators, and platforms
    based on the provided configuration entry. It performs firmware version
    checks, handles device ID validation, and sets up data coordinators for
    state updates and device tracking.

    Parameters
    ----------
    hass : HomeAssistant
        The Home Assistant instance.
    entry : ConfigEntry
        The configuration entry containing OPNsense connection details.

    Returns:
    -------
    bool
        True if setup was successful, False otherwise.

    Raises:
    ------
    Various exceptions may be raised during client initialization or firmware
    checks, but they are handled internally with appropriate logging and issue
    creation.

    """
    config: Mapping[str, Any] = entry.data
    options: Mapping[str, Any] = entry.options

    url: str = config[CONF_URL]
    username: str = config[CONF_USERNAME]
    password: str = config[CONF_PASSWORD]
    verify_ssl: bool = config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    device_tracker_enabled: bool = options.get(
        CONF_DEVICE_TRACKER_ENABLED, DEFAULT_DEVICE_TRACKER_ENABLED
    )
    config_device_id: str = config[CONF_DEVICE_UNIQUE_ID]

    client = OPNsenseClient(
        url=url,
        username=username,
        password=password,
        session=async_create_clientsession(
            hass=hass,
            raise_for_status=False,
            cookie_jar=aiohttp.CookieJar(unsafe=is_private_ip(url)),
        ),
        opts={"verify_ssl": verify_ssl},
        name=entry.title,
    )

    scan_interval: int = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    _LOGGER.info("Starting the OPNsense integration %s", VERSION)

    coordinator = OPNsenseDataUpdateCoordinator(
        hass=hass,
        name=f"{entry.title} state",
        update_interval=timedelta(seconds=scan_interval),
        client=client,
        device_unique_id=config_device_id,
        config_entry=entry,
    )

    # Trigger repair task and shutdown if device id has changed
    router_device_id: str | None = await client.get_device_unique_id(
        expected_id=config_device_id
    )
    _LOGGER.debug(
        "[init async_setup_entry]: config device id: %s, router device id: %s",
        config_device_id,
        router_device_id,
    )
    if router_device_id != config_device_id and router_device_id:
        ir.async_create_issue(
            hass=hass,
            domain=DOMAIN,
            issue_id=f"{config_device_id}_device_id_mismatched",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="device_id_mismatched",
        )
        _LOGGER.error(
            "OPNsense Device ID has changed which indicates new or changed hardware. "
            "In order to accommodate this, the OPNsense integration needs to be removed and reinstalled for this router. "
            "The OPNsense integration is shutting down"
        )
        await coordinator.async_shutdown()
        return False

    firmware: str | None = await client.get_host_firmware_version()
    _LOGGER.info("OPNsense Firmware %s", firmware)
    try:
        if awesomeversion.AwesomeVersion(firmware) < awesomeversion.AwesomeVersion(
            OPNSENSE_MIN_FIRMWARE
        ):
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"{config_device_id}_opnsense_below_min_firmware_{OPNSENSE_MIN_FIRMWARE}",
                is_fixable=False,
                is_persistent=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.ERROR,
                translation_key="below_min_firmware",
                translation_placeholders={
                    "version": str(VERSION),
                    "min_firmware": str(OPNSENSE_MIN_FIRMWARE),
                    "firmware": firmware or "Unknown",
                },
            )
            await coordinator.async_shutdown()
            return False
        ir.async_delete_issue(
            hass,
            DOMAIN,
            f"{config_device_id}_opnsense_below_min_firmware_{OPNSENSE_MIN_FIRMWARE}",
        )
    except (
        awesomeversion.exceptions.AwesomeVersionCompareException,
        TypeError,
        ValueError,
    ):
        _LOGGER.warning("Unable to confirm OPNsense Firmware version")

    await coordinator.async_config_entry_first_refresh()

    platforms: list[Platform] = PLATFORMS.copy()
    device_tracker_coordinator = None
    if not device_tracker_enabled and Platform.DEVICE_TRACKER in platforms:
        platforms.remove(Platform.DEVICE_TRACKER)
    else:
        device_tracker_scan_interval = options.get(
            CONF_DEVICE_TRACKER_SCAN_INTERVAL, DEFAULT_DEVICE_TRACKER_SCAN_INTERVAL
        )

        device_tracker_coordinator = OPNsenseDataUpdateCoordinator(
            hass=hass,
            name=f"{entry.title} Device Tracker state",
            update_interval=timedelta(seconds=device_tracker_scan_interval),
            client=client,
            config_entry=entry,
            device_unique_id=config_device_id,
            device_tracker_coordinator=True,
        )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = client

    entry.runtime_data = OPNsenseData(
        coordinator=coordinator,
        device_tracker_coordinator=device_tracker_coordinator,
        opnsense_client=client,
        device_unique_id=config_device_id,
        loaded_platforms=platforms,
    )

    if device_tracker_enabled and device_tracker_coordinator:
        # Fetch initial data so we have data when entities subscribe
        await device_tracker_coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove OPNsense devices that are not device tracker devices and have no linked entities.

    This function checks if an OPNsense device can be safely removed. It prevents
    removal of device tracker devices and devices that still have linked entities.

    Parameters
    ----------
    hass : HomeAssistant
        The Home Assistant instance.
    config_entry : ConfigEntry
        The configuration entry for the OPNsense integration.
    device_entry : dr.DeviceEntry
        The device entry to be removed.

    Returns:
    -------
    bool
        True if the device can be removed, False otherwise.

    """
    if device_entry.via_device_id:
        _LOGGER.error(
            "Remove OPNsense Device Tracker Devices via the Integration Configuration"
        )
        return False
    entity_registry = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if ent.device_id == device_entry.id:
            _LOGGER.error(
                "Cannot remove OPNsense Devices with linked entities at this time"
            )
            return False
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the OPNsense integration configuration entry.

    This function unloads all platforms associated with the configuration entry,
    closes the OPNsense client connection, and cleans up the entry data.

    Parameters
    ----------
    hass : HomeAssistant
        The Home Assistant instance.
    entry : ConfigEntry
        The configuration entry to unload.

    Returns:
    -------
    bool
        True if unloading was successful, False otherwise.

    """
    _LOGGER.info("Unloading: %s", entry.as_dict())
    platforms: list[Platform] = getattr(entry.runtime_data, LOADED_PLATFORMS)
    client: OPNsenseClient = getattr(entry.runtime_data, OPNSENSE_CLIENT)
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, platforms)

    await client.async_close()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
