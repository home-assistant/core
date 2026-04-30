"""The Lunatone integration."""

import logging
from typing import Final

from lunatone_rest_api_client import Auth, DALIBroadcast, Devices, Info

from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .config_flow import LunatoneConfigFlow
from .const import DOMAIN, MANUFACTURER
from .coordinator import (
    LunatoneConfigEntry,
    LunatoneData,
    LunatoneDevicesDataUpdateCoordinator,
    LunatoneInfoDataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS: Final[list[Platform]] = [Platform.LIGHT]


async def _update_unique_id(
    hass: HomeAssistant, entry: LunatoneConfigEntry, new_unique_id: str
) -> None:
    _LOGGER.debug("Update unique ID")

    # Update all associated entities
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    for entity in entities:
        parts = list(entity.unique_id.partition("-"))
        parts[0] = new_unique_id

        entity_registry.async_update_entity(
            entity.entity_id, new_unique_id="".join(parts)
        )

    # Update all associated devices
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    for device in devices:
        identifier = device.identifiers.pop()
        parts = list(identifier[1].partition("-"))
        parts[0] = new_unique_id

        device_registry.async_update_device(
            device.id, new_identifiers={(identifier[0], "".join(parts))}
        )

    # Update the config entry itself
    hass.config_entries.async_update_entry(
        entry,
        unique_id=new_unique_id,
        minor_version=LunatoneConfigFlow.MINOR_VERSION,
        version=LunatoneConfigFlow.VERSION,
    )

    _LOGGER.debug("Update of unique ID successful")


async def async_setup_entry(hass: HomeAssistant, entry: LunatoneConfigEntry) -> bool:
    """Set up Lunatone from a config entry."""
    auth_api = Auth(async_get_clientsession(hass), entry.data[CONF_URL])
    info_api = Info(auth_api)
    devices_api = Devices(info_api)

    coordinator_info = LunatoneInfoDataUpdateCoordinator(hass, entry, info_api)
    await coordinator_info.async_config_entry_first_refresh()

    if info_api.data is None or info_api.serial_number is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="missing_device_info"
        )

    if info_api.uid is not None:
        new_unique_id = info_api.uid.replace("-", "")
        if new_unique_id != entry.unique_id:
            await _update_unique_id(hass, entry, new_unique_id)

    assert entry.unique_id

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        name=info_api.name,
        manufacturer=MANUFACTURER,
        sw_version=info_api.version,
        hw_version=coordinator_info.data.device.pcb,
        configuration_url=entry.data[CONF_URL],
        serial_number=str(info_api.serial_number),
        model=info_api.product_name,
        model_id=(
            f"{coordinator_info.data.device.article_number}{coordinator_info.data.device.article_info}"
        ),
    )

    coordinator_devices = LunatoneDevicesDataUpdateCoordinator(hass, entry, devices_api)
    await coordinator_devices.async_config_entry_first_refresh()

    dali_line_broadcasts = [
        DALIBroadcast(auth_api, int(line)) for line in coordinator_info.data.lines
    ]

    entry.runtime_data = LunatoneData(
        coordinator_info,
        coordinator_devices,
        dali_line_broadcasts,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LunatoneConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
