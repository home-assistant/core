"""Support for IKEA Tradfri."""

from __future__ import annotations

from datetime import datetime, timedelta

from pytradfri import Gateway, RequestError
from pytradfri.api.aiocoap_api import APIFactory
from pytradfri.device import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_GATEWAY_ID, CONF_IDENTITY, CONF_KEY, DOMAIN, LOGGER
from .coordinator import TradfriDeviceDataUpdateCoordinator
from .migration import migrate_device_identifier
from .models import TradfriData

PLATFORMS = [
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]
SIGNAL_GW = "tradfri.gw_status"
TIMEOUT_API = 30


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Create a gateway."""
    # Migrate old integer device identifier to string, added in core-2022.7.0.
    migrate_device_identifier(hass, entry)

    factory = await APIFactory.init(
        entry.data[CONF_HOST],
        psk_id=entry.data[CONF_IDENTITY],
        psk=entry.data[CONF_KEY],
    )

    async def on_hass_stop(event: Event) -> None:
        """Close connection when hass stops."""
        await factory.shutdown()

    # Setup listeners
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    api = factory.request
    gateway = Gateway()

    try:
        gateway_info = await api(gateway.get_gateway_info(), timeout=TIMEOUT_API)
        devices_commands = await api(gateway.get_devices(), timeout=TIMEOUT_API)
        devices = await api(devices_commands, timeout=TIMEOUT_API)

    except RequestError as exc:
        await factory.shutdown()
        raise ConfigEntryNotReady from exc

    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={(DOMAIN, entry.data[CONF_GATEWAY_ID])},
        manufacturer="IKEA of Sweden",
        name="Gateway",
        # They just have 1 gateway model. Type is not exposed yet.
        model="E1526",
        sw_version=gateway_info.firmware_version,
    )

    remove_stale_devices(hass, entry, devices)

    # Setup the device coordinators
    coordinators: list[TradfriDeviceDataUpdateCoordinator] = []

    for device in devices:
        coordinator = TradfriDeviceDataUpdateCoordinator(
            hass=hass, config_entry=entry, api=api, device=device
        )
        await coordinator.async_config_entry_first_refresh()

        entry.async_on_unload(
            async_dispatcher_connect(hass, SIGNAL_GW, coordinator.set_hub_available)
        )
        coordinators.append(coordinator)

    tradfri_data = TradfriData(
        api=api, coordinators=coordinators, factory=factory, gateway=gateway
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = tradfri_data

    async def async_keep_alive(now: datetime) -> None:
        if hass.is_stopping:
            return

        gw_status = True
        try:
            await api(gateway.get_gateway_info())
        except RequestError:
            LOGGER.error("Keep-alive failed")
            gw_status = False

        async_dispatcher_send(hass, SIGNAL_GW, gw_status)

    entry.async_on_unload(
        async_track_time_interval(hass, async_keep_alive, timedelta(seconds=60))
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        tradfri_data: TradfriData = hass.data[DOMAIN].pop(entry.entry_id)
        factory = tradfri_data.factory
        await factory.shutdown()

    return unload_ok


@callback
def remove_stale_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, devices: list[Device]
) -> None:
    """Remove stale devices from device registry."""
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    all_device_ids = {str(device.id) for device in devices}

    for device_entry in device_entries:
        device_id: str | None = None
        gateway_id: str | None = None

        for identifier in device_entry.identifiers:
            if identifier[0] != DOMAIN:
                continue

            # The device id in the identifier was not copied from integer to string
            # when setting entity device info. Copy here to make sure it's a string.
            _id = str(identifier[1])

            # Identify gateway device.
            if _id == config_entry.data[CONF_GATEWAY_ID]:
                gateway_id = _id
                break

            device_id = _id
            break

        if gateway_id is not None:
            # Do not remove gateway device entry.
            continue

        if device_id is None or device_id not in all_device_ids:
            # If device_id is None an invalid device entry was found for this config entry.
            # If the device_id is not in existing device ids it's a stale device entry.
            # Remove config entry from this device entry in either case.
            device_registry.async_update_device(
                device_entry.id, remove_config_entry_id=config_entry.entry_id
            )
