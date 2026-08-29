"""The Bravia TV integration."""

from typing import Final

from aiohttp import CookieJar
from pybravia import BraviaClient, BraviaError

from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import ATTR_MAC, CONF_USE_SSL
from .coordinator import BraviaTVConfigEntry, BraviaTVCoordinator

PLATFORMS: Final[list[Platform]] = [
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
]


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: BraviaTVConfigEntry
) -> bool:
    """Migrate old config entries to the new unique_id based on MAC."""
    if config_entry.version > 1:
        return True

    if config_entry.version == 1:
        host = config_entry.data[CONF_HOST]
        mac = config_entry.data[CONF_MAC]
        ssl = config_entry.data.get(CONF_USE_SSL, False)

        session = async_create_clientsession(
            hass, cookie_jar=CookieJar(unsafe=True, quote_cookie=False)
        )
        client = BraviaClient(host, mac, session=session, ssl=ssl)

        try:
            system_info = await client.get_system_info()
        except BraviaError:
            return False

        new_unique_id = dr.format_mac(system_info[ATTR_MAC])

        old_unique_id = config_entry.unique_id or ""

        if old_unique_id != new_unique_id:
            ent_reg = er.async_get(hass)
            for entity in er.async_entries_for_config_entry(
                ent_reg, config_entry.entry_id
            ):
                if entity.unique_id == old_unique_id:
                    ent_reg.async_update_entity(
                        entity.entity_id, new_unique_id=new_unique_id
                    )
                elif entity.unique_id is not None and entity.unique_id.startswith(
                    f"{old_unique_id}_"
                ):
                    suffix = entity.unique_id[len(old_unique_id) :]
                    ent_reg.async_update_entity(
                        entity.entity_id, new_unique_id=f"{new_unique_id}{suffix}"
                    )

            dev_reg = dr.async_get(hass)
            for device in dr.async_entries_for_config_entry(
                dev_reg, config_entry.entry_id
            ):
                dev_reg.async_update_device(device.id, new_identifiers=set())

        hass.config_entries.async_update_entry(
            config_entry, unique_id=new_unique_id, version=2
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: BraviaTVConfigEntry
) -> bool:
    """Set up a config entry."""
    host = config_entry.data[CONF_HOST]
    mac = config_entry.data[CONF_MAC]
    ssl = config_entry.data.get(CONF_USE_SSL, False)

    session = async_create_clientsession(
        hass, cookie_jar=CookieJar(unsafe=True, quote_cookie=False)
    )
    client = BraviaClient(host, mac, session=session, ssl=ssl)
    coordinator = BraviaTVCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=client,
    )
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def async_ssdp_callback(
        discovery_info: SsdpServiceInfo, change: ssdp.SsdpChange
    ) -> None:
        await coordinator.async_request_refresh()

    config_entry.async_on_unload(
        await ssdp.async_register_callback(
            hass,
            async_ssdp_callback,
            {"nt": "urn:schemas-upnp-org:device:MediaRenderer:1", "_host": host},
        )
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: BraviaTVConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def update_listener(
    hass: HomeAssistant, config_entry: BraviaTVConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
