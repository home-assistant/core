"""Support for IKEA Tradfri."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pytradfri import Gateway, RequestError
from pytradfri.api.aiocoap_api import APIFactory
from pytradfri.command import Command
from pytradfri.device import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_GATEWAY_ID,
    CONF_IDENTITY,
    CONF_KEY,
    COORDINATOR,
    COORDINATOR_LIST,
    DOMAIN,
    FACTORY,
    KEY_API,
    LOGGER,
)
from .coordinator import TradfriDeviceDataUpdateCoordinator

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
    tradfri_data: dict[str, Any] = {}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = tradfri_data

    factory = await APIFactory.init(
        entry.data[CONF_HOST],
        psk_id=entry.data[CONF_IDENTITY],
        psk=entry.data[CONF_KEY],
    )
    tradfri_data[FACTORY] = factory  # Used for async_unload_entry

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
        devices_commands: Command = await api(
            gateway.get_devices(), timeout=TIMEOUT_API
        )
        devices: list[Device] = await api(devices_commands, timeout=TIMEOUT_API)

    except RequestError as exc:
        await factory.shutdown()
        raise ConfigEntryNotReady from exc

    migrate_entity_unique_ids(hass, entry.entry_id)

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
    coordinator_data = {
        CONF_GATEWAY_ID: gateway,
        KEY_API: api,
        COORDINATOR_LIST: [],
    }

    for device in devices:
        coordinator = TradfriDeviceDataUpdateCoordinator(
            hass=hass, config_entry=entry, api=api, device=device
        )
        await coordinator.async_config_entry_first_refresh()

        entry.async_on_unload(
            async_dispatcher_connect(hass, SIGNAL_GW, coordinator.set_hub_available)
        )
        coordinator_data[COORDINATOR_LIST].append(coordinator)

    tradfri_data[COORDINATOR] = coordinator_data

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


def migrate_entity_unique_ids(hass: HomeAssistant, ConfigEntryId: str) -> None:
    """Migrate old non-unique identifiers to new unique identifiers."""

    device_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_reg, ConfigEntryId):
        # Remove non-primary config entry ID from config_entries if present
        config_entries = device.config_entries
        if len(config_entries) > 1:
            # Non-primary config entry exists, remove it
            for config_entry in config_entries:
                if config_entry != ConfigEntryId:
                    device_reg.async_update_device(
                        device.id, remove_config_entry_id=config_entry
                    )

    entity_reg = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_reg, ConfigEntryId):
        # 4 types of unique_id:
        # 1) <Tradfri gateway ID>
        # 2) light-<Tradfri gateway ID>-<Tradfri gateway's own device ID>
        # 3) <Tradfri gateway ID>-<Tradfri gateway's own device ID>
        # 4) <Tradfri gateway ID>-<Tradfri gateway's own device ID>-battery_level
        # Need to extract 'Tradfri gateway's own device ID' from string and match against device.
        # If device is found, update device's identifiers to:
        # {DOMAIN, "<Tradfri gateway ID>-<Tradfri gateway's own device ID>"}
        unique_id_parts = entity.unique_id.split("-")
        if len(unique_id_parts) > 1:
            if unique_id_parts[0].find("light") > -1:
                tradfri_device_id = unique_id_parts[2]
                tradfri_gateway_id = unique_id_parts[1]
            else:
                tradfri_device_id = unique_id_parts[1]
                tradfri_gateway_id = unique_id_parts[0]

            if device := device_reg.async_get_device(  # type: ignore[assignment]
                identifiers={(DOMAIN, int(tradfri_device_id))}  # type: ignore[arg-type]
            ):
                device_reg.async_update_device(
                    device.id,
                    new_identifiers={
                        (DOMAIN, f"{tradfri_gateway_id}-{tradfri_device_id}")
                    },
                )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        tradfri_data = hass.data[DOMAIN].pop(entry.entry_id)
        factory = tradfri_data[FACTORY]
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
    all_device_ids = {device.id for device in devices}

    for device_entry in device_entries:
        device_id: str | None = None
        gateway_id: str | None = None

        for identifier in device_entry.identifiers:
            if identifier[0] != DOMAIN:
                continue

            _id = identifier[1]

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
