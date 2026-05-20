"""The Connectivity Monitor integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DNS_SERVER,
    CONF_INTERVAL,
    CONF_PROTOCOL,
    CONF_TARGETS,
    DEFAULT_DNS_SERVER,
    DEFAULT_INTERVAL,
    DOMAIN,
    NON_NETWORK_PROTOCOLS,
    PROTOCOL_BLUETOOTH,
    PROTOCOL_ESPHOME,
    PROTOCOL_MATTER,
    PROTOCOL_ZHA,
    VERSION,
)
from .coordinator import (
    ConnectivityMonitorConfigEntry,
    ConnectivityMonitorCoordinator,
    ConnectivityMonitorRuntimeData,
)
from .sensor import AlertHandler

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate an old combined entry (v1) into three typed entries (v2)."""
    if config_entry.version == 1:
        _LOGGER.info(
            "Connectivity Monitor: migrating config entry '%s' from v1 to v2 "
            "(splitting into typed entries)",
            config_entry.title,
        )

        targets = list(config_entry.data.get(CONF_TARGETS, []))
        interval = config_entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL)
        dns_server = config_entry.data.get(CONF_DNS_SERVER, DEFAULT_DNS_SERVER)

        network_targets = [
            t for t in targets if t.get(CONF_PROTOCOL) not in NON_NETWORK_PROTOCOLS
        ]
        zha_targets = [t for t in targets if t.get(CONF_PROTOCOL) == PROTOCOL_ZHA]
        matter_targets = [t for t in targets if t.get(CONF_PROTOCOL) == PROTOCOL_MATTER]
        esphome_targets = [
            t for t in targets if t.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME
        ]
        bluetooth_targets = [
            t for t in targets if t.get(CONF_PROTOCOL) == PROTOCOL_BLUETOOTH
        ]

        # Schedule creation of a ZigBee Monitor entry (if ZHA devices exist)
        if zha_targets:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_TARGETS: zha_targets,
                        CONF_INTERVAL: interval,
                        CONF_DNS_SERVER: dns_server,
                        "entry_type": "zha",
                    },
                )
            )

        # Schedule creation of a Matter Monitor entry (if Matter devices exist)
        if matter_targets:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_TARGETS: matter_targets,
                        CONF_INTERVAL: interval,
                        CONF_DNS_SERVER: dns_server,
                        "entry_type": "matter",
                    },
                )
            )

        # Schedule creation of an ESPHome Monitor entry (if ESPHome devices exist)
        if esphome_targets:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_TARGETS: esphome_targets,
                        CONF_INTERVAL: interval,
                        CONF_DNS_SERVER: dns_server,
                        "entry_type": "esphome",
                    },
                )
            )

        # Schedule creation of a Bluetooth Monitor entry (if Bluetooth devices exist)
        if bluetooth_targets:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_TARGETS: bluetooth_targets,
                        CONF_INTERVAL: interval,
                        CONF_DNS_SERVER: dns_server,
                        "entry_type": "bluetooth",
                    },
                )
            )

        # Convert the current entry into the Network Monitor entry
        hass.config_entries.async_update_entry(
            config_entry,
            title="Network Monitor",
            unique_id="connectivity_monitor_network",
            data={
                CONF_TARGETS: network_targets,
                CONF_INTERVAL: interval,
                CONF_DNS_SERVER: dns_server,
            },
            version=2,
        )

        _LOGGER.info(
            "Connectivity Monitor: migration complete — %d network, %d ZigBee, %d Matter, %d ESPHome, %d Bluetooth devices",
            len(network_targets),
            len(zha_targets),
            len(matter_targets),
            len(esphome_targets),
            len(bluetooth_targets),
        )

    return True


# We only need the sensor platform since alerts are handled within the sensor code
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Connectivity Monitor component."""
    card_base_url = "/connectivity_monitor/connectivity_monitor_card.js"
    card_url = f"{card_base_url}?v={VERSION}"

    # Serve www/ folder so the card JS is reachable via HTTP
    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/connectivity_monitor",
                    str(Path(__file__).parent / "www"),
                    cache_headers=False,
                )
            ]
        )
    except (OSError, ValueError) as err:
        _LOGGER.warning("Connectivity Monitor: could not register static path: %s", err)

    # Register card as a Lovelace resource (same as Settings > Dashboards > Resources).
    # Must run after HA is fully started so the lovelace storage is available.
    async def _register_lovelace_resource(_event=None):
        try:
            from homeassistant.components.lovelace.const import (  # noqa: PLC0415  # pylint: disable=hass-component-root-import
                LOVELACE_DATA,
            )

            ll = hass.data.get(LOVELACE_DATA)
            if ll is None:
                return
            resources = getattr(ll, "resources", None)
            if resources is None:
                return
            await resources.async_load()
            current_resources = list(resources.async_items())
            if any(r.get("url") == card_url for r in current_resources):
                return

            for resource in current_resources:
                resource_url = resource.get("url", "")
                if resource_url == card_base_url or resource_url.startswith(
                    f"{card_base_url}?"
                ):
                    await resources.async_update_item(resource["id"], {"url": card_url})
                    _LOGGER.info(
                        "Connectivity Monitor: Lovelace resource updated to %s",
                        card_url,
                    )
                    return

            await resources.async_create_item({"res_type": "module", "url": card_url})
            _LOGGER.info(
                "Connectivity Monitor: Lovelace resource registered at %s", card_url
            )
        except (ImportError, AttributeError, TypeError) as err:
            _LOGGER.warning(
                "Connectivity Monitor: could not register Lovelace resource: %s", err
            )

    hass.bus.async_listen_once("homeassistant_started", _register_lovelace_resource)

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConnectivityMonitorConfigEntry
) -> bool:
    """Set up Connectivity Monitor from a config entry."""
    alert_handler = AlertHandler(hass)
    coordinator = ConnectivityMonitorCoordinator(
        hass,
        list(entry.data[CONF_TARGETS]),
        entry.data[CONF_INTERVAL],
        entry.data[CONF_DNS_SERVER],
        entry,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = ConnectivityMonitorRuntimeData(
        coordinator=coordinator,
        alert_handler=alert_handler,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConnectivityMonitorConfigEntry
) -> bool:
    """Unload a config entry."""
    # Clean up alert handler before unloading platforms to stop any
    # in-flight callbacks from firing during teardown.
    if hasattr(entry, "runtime_data"):
        await entry.runtime_data.alert_handler.async_cleanup()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and hasattr(entry, "runtime_data"):
        del entry.runtime_data
    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant, entry: ConnectivityMonitorConfigEntry
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
