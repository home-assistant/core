"""The WattWächter integration."""

import logging

from aio_wattwaechter import Wattwaechter, WattwaechterConnectionError

from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import WattwaechterConfigEntry, WattwaechterCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.UPDATE]


async def async_setup_entry(
    hass: HomeAssistant, entry: WattwaechterConfigEntry
) -> None:
    """Set up WattWächter from a config entry."""
    host = entry.data[CONF_HOST]
    token = entry.data.get(CONF_TOKEN)

    session = async_get_clientsession(hass)
    client = Wattwaechter(host, token=token, session=session)

    try:
        await client.alive()
    except WattwaechterConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host},
        ) from err

    coordinator = WattwaechterCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: WattwaechterConfigEntry
) -> None:
    """Unload a WattWächter config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: WattwaechterConfigEntry
) -> None:
    """Migrate an old config entry."""
    if entry.minor_version < 2:
        # Discovery used to strip only the WWP- prefix of the mDNS id record, so
        # gas/water devices were stored as WWGW-<MAC> instead of the bare MAC.
        old_id: str = entry.data[CONF_DEVICE_ID]
        new_id = old_id.rpartition("-")[2]
        duplicate = any(
            other.unique_id == new_id
            for other in hass.config_entries.async_entries(DOMAIN)
            if other.entry_id != entry.entry_id
        )
        if new_id != old_id and duplicate:
            _LOGGER.warning(
                "Device %s is configured twice; keeping the ID %s of this entry",
                new_id,
                old_id,
            )
        elif new_id != old_id:
            device_registry = dr.async_get(hass)
            for device in dr.async_entries_for_config_entry(
                device_registry, entry.entry_id
            ):
                if (DOMAIN, old_id) in device.identifiers:
                    device_registry.async_update_device(
                        device.id, new_identifiers={(DOMAIN, new_id)}
                    )

            @callback
            def _migrate_unique_id(
                entity_entry: er.RegistryEntry,
            ) -> dict[str, str] | None:
                unique_id = entity_entry.unique_id
                if unique_id == old_id or unique_id.startswith(f"{old_id}_"):
                    return {"new_unique_id": new_id + unique_id[len(old_id) :]}
                return None

            await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_DEVICE_ID: new_id},
                unique_id=new_id if entry.unique_id == old_id else entry.unique_id,
            )
        hass.config_entries.async_update_entry(entry, minor_version=2)
