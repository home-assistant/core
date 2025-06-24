"""The devolo Home Network integration."""

from __future__ import annotations

import logging
from typing import Any

from devolo_plc_api import Device
from devolo_plc_api.exceptions.device import DeviceNotFound

from homeassistant.components import zeroconf
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    CONNECTED_PLC_DEVICES,
    CONNECTED_WIFI_CLIENTS,
    DOMAIN,
    LAST_RESTART,
    NEIGHBORING_WIFI_NETWORKS,
    REGULAR_FIRMWARE,
    SWITCH_GUEST_WIFI,
    SWITCH_LEDS,
)
from .coordinator import (
    DevoloDataUpdateCoordinator,
    DevoloFirmwareUpdateCoordinator,
    DevoloHomeNetworkConfigEntry,
    DevoloHomeNetworkData,
    DevoloLedSettingsGetCoordinator,
    DevoloLogicalNetworkCoordinator,
    DevoloUptimeGetCoordinator,
    DevoloWifiConnectedStationsGetCoordinator,
    DevoloWifiGuestAccessGetCoordinator,
    DevoloWifiNeighborAPsGetCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: DevoloHomeNetworkConfigEntry
) -> bool:
    """Set up devolo Home Network from a config entry."""
    zeroconf_instance = await zeroconf.async_get_async_instance(hass)
    async_client = get_async_client(hass)

    try:
        device = Device(
            ip=entry.data[CONF_IP_ADDRESS], zeroconf_instance=zeroconf_instance
        )
        await device.async_connect(session_instance=async_client)
        device.password = entry.data.get(
            CONF_PASSWORD,
            "",  # This key was added in HA Core 2022.6
        )
    except DeviceNotFound as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
            translation_placeholders={"ip_address": entry.data[CONF_IP_ADDRESS]},
        ) from err

    entry.runtime_data = DevoloHomeNetworkData(device=device, coordinators={})

    async def disconnect(event: Event) -> None:
        """Disconnect from device."""
        await device.async_disconnect()

    coordinators: dict[str, DevoloDataUpdateCoordinator[Any]] = {}
    if device.plcnet:
        coordinators[CONNECTED_PLC_DEVICES] = DevoloLogicalNetworkCoordinator(
            hass,
            _LOGGER,
            config_entry=entry,
        )
    if device.device and "led" in device.device.features:
        coordinators[SWITCH_LEDS] = DevoloLedSettingsGetCoordinator(
            hass,
            _LOGGER,
            config_entry=entry,
        )
    if device.device and "restart" in device.device.features:
        coordinators[LAST_RESTART] = DevoloUptimeGetCoordinator(
            hass,
            _LOGGER,
            config_entry=entry,
        )
    if device.device and "update" in device.device.features:
        coordinators[REGULAR_FIRMWARE] = DevoloFirmwareUpdateCoordinator(
            hass,
            _LOGGER,
            config_entry=entry,
        )
    if device.device and "wifi1" in device.device.features:
        coordinators[CONNECTED_WIFI_CLIENTS] = (
            DevoloWifiConnectedStationsGetCoordinator(
                hass,
                _LOGGER,
                config_entry=entry,
            )
        )
        coordinators[NEIGHBORING_WIFI_NETWORKS] = DevoloWifiNeighborAPsGetCoordinator(
            hass,
            _LOGGER,
            config_entry=entry,
        )
        coordinators[SWITCH_GUEST_WIFI] = DevoloWifiGuestAccessGetCoordinator(
            hass,
            _LOGGER,
            config_entry=entry,
        )

    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data.coordinators = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, platforms(device))

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect)
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DevoloHomeNetworkConfigEntry
) -> bool:
    """Unload a config entry."""
    device = entry.runtime_data.device
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, platforms(device)
    )
    if unload_ok:
        await device.async_disconnect()

    return unload_ok


@callback
def platforms(device: Device) -> set[Platform]:
    """Assemble supported platforms."""
    supported_platforms = {Platform.BUTTON, Platform.SENSOR, Platform.SWITCH}
    if device.plcnet:
        supported_platforms.add(Platform.BINARY_SENSOR)
    if device.device and "wifi1" in device.device.features:
        supported_platforms.add(Platform.DEVICE_TRACKER)
        supported_platforms.add(Platform.IMAGE)
    if device.device and "update" in device.device.features:
        supported_platforms.add(Platform.UPDATE)
    return supported_platforms
