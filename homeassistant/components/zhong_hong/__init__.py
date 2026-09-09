"""The ZhongHong HVAC integration."""

from collections.abc import Iterable
from dataclasses import dataclass

from zhong_hong_hvac.hub import ZhongHongGateway
from zhong_hong_hvac.hvac import HVAC as ZhongHongHVAC

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import CONF_GATEWAY_ADDRESS, DOMAIN

PLATFORMS: list[Platform] = [Platform.CLIMATE]

type DeviceAddress = tuple[int, int]


@dataclass
class ZhongHongData:
    """What a loaded config entry holds.

    The air conditioners are found once, when the entry is set up: discovery
    needs the listener thread stopped, so the gateway cannot be asked again
    while the entry is running.
    """

    hub: ZhongHongGateway
    devices: dict[DeviceAddress, ZhongHongHVAC]


type ZhongHongConfigEntry = ConfigEntry[ZhongHongData]


def device_unique_id(entry: ZhongHongConfigEntry, address: DeviceAddress) -> str:
    """Return the unique ID of the air conditioner at an address."""
    return f"{entry.entry_id}_{address[0]}_{address[1]}"


def legacy_device_unique_id(address: DeviceAddress) -> str:
    """Return the identifier the YAML platform gave the air conditioner.

    It carried only the address on the bus, so two gateways with an air
    conditioner at the same address, which `(1, 1)` commonly is, produced the
    same one and the second entity was dropped. Entities are moved off it on
    setup; it is still needed to find them.
    """
    return f"zhong_hong_hvac_{address[0]}_{address[1]}"


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


def _connect(hub: ZhongHongGateway) -> dict[DeviceAddress, ZhongHongHVAC]:
    """Ask the gateway what is on its bus, then start listening to it.

    Discovery has to finish before the listener thread starts, because the two
    read from the same socket. All of it blocks, so it runs as one executor
    job rather than hopping back to the event loop in between.
    """
    addresses = hub.discovery_ac()
    if not addresses:
        return {}

    # Creating the device registers it with the hub, which is what routes the
    # gateway's pushes to it.
    devices = {address: ZhongHongHVAC(hub, *address) for address in addresses}

    hub.start_listen()

    # The gateway reports a unit only when it changes, so without asking once
    # here the entities would have no state until someone touched a unit.
    if not hub.query_all_status():
        raise OSError(f"The gateway at {hub.ip_addr} did not answer the first query")

    return devices


async def _async_connect(
    hass: HomeAssistant, hub: ZhongHongGateway
) -> dict[DeviceAddress, ZhongHongHVAC]:
    """Connect to the gateway, or say why the entry is not ready."""
    try:
        devices = await hass.async_add_executor_job(_connect, hub)
    except OSError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": hub.ip_addr},
        ) from err

    if not devices:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="no_devices_found",
            translation_placeholders={"host": hub.ip_addr},
        )

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

    entry.runtime_data = ZhongHongData(hub, devices)
    _async_migrate_unique_ids(hass, entry, devices)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZhongHongConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
