"""The ZhongHong HVAC integration."""

from collections.abc import Iterable

from zhong_hong_hvac.hub import ZhongHongGateway
from zhong_hong_hvac.hvac import HVAC as ZhongHongHVAC

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import CONF_GATEWAY_ADDRESS, DOMAIN
from .coordinator import (
    DeviceAddress,
    ZhongHongConfigEntry,
    ZhongHongCoordinator,
    ZhongHongData,
    device_unique_id,
    legacy_device_unique_id,
)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


@callback
def _async_migrate_unique_ids(
    hass: HomeAssistant, entry: ZhongHongConfigEntry, addresses: Iterable[DeviceAddress]
) -> None:
    """Move the entities off the identifier the YAML platform gave them.

    That identifier was the address on the bus and nothing else, so a second
    gateway with an air conditioner at the same address produced an entity
    Home Assistant refused to add. Moving them keeps their entity IDs, and
    with those their recorded history.

    Only entities this entry owns are moved. An entity the YAML platform
    registered has no owner yet, and is claimed by whichever entry sets up
    first; there can only be one, since the old identifier is what stopped a
    second from ever being created.
    """
    entity_registry = er.async_get(hass)

    for address in addresses:
        entity_id = entity_registry.async_get_entity_id(
            CLIMATE_DOMAIN, DOMAIN, legacy_device_unique_id(address)
        )
        if entity_id is None:
            continue

        registry_entry = entity_registry.async_get(entity_id)
        if registry_entry is None or registry_entry.config_entry_id not in (
            None,
            entry.entry_id,
        ):
            continue

        entity_registry.async_update_entity(
            entity_id, new_unique_id=device_unique_id(entry, address)
        )


async def _async_connect(
    hass: HomeAssistant, hub: ZhongHongGateway
) -> dict[DeviceAddress, ZhongHongHVAC]:
    """Ask the gateway what is on its bus, then start listening to it.

    Discovery has to finish before the listener thread starts, because the two
    read from the same socket.
    """
    try:
        addresses = await hass.async_add_executor_job(hub.discovery_ac)
    except OSError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": hub.ip_addr},
        ) from err

    if not addresses:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="no_devices_found",
            translation_placeholders={"host": hub.ip_addr},
        )

    # Creating the device registers it with the hub, which is what routes the
    # gateway's pushes to it.
    devices = {address: ZhongHongHVAC(hub, *address) for address in addresses}

    await hass.async_add_executor_job(hub.start_listen)
    return devices


async def async_setup_entry(hass: HomeAssistant, entry: ZhongHongConfigEntry) -> bool:
    """Set up ZhongHong from a config entry."""
    hub = ZhongHongGateway(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_GATEWAY_ADDRESS],
    )

    async def _async_close() -> None:
        await hass.async_add_executor_job(hub.stop_listen)

    # Registered before the socket is opened rather than after: the gateway
    # takes one connection at a time, so a discovery that fails half way has
    # to give its socket back or the retry is refused by our own.
    entry.async_on_unload(_async_close)

    devices = await _async_connect(hass, hub)

    coordinator = ZhongHongCoordinator(hass, entry, hub, devices)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = ZhongHongData(hub, devices, coordinator)
    _async_migrate_unique_ids(hass, entry, devices)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZhongHongConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
