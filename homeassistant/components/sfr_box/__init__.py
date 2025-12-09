"""SFR Box."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sfrbox_api.bridge import SFRBox
from sfrbox_api.exceptions import SFRBoxAuthenticationError, SFRBoxError

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS, PLATFORMS_WITH_AUTH
from .coordinator import SFRConfigEntry, SFRDataUpdateCoordinator, SFRRuntimeData


async def async_setup_entry(hass: HomeAssistant, entry: SFRConfigEntry) -> bool:
    """Set up SFR box as config entry."""
    box = SFRBox(ip=entry.data[CONF_HOST], client=async_get_clientsession(hass))
    platforms = PLATFORMS
    if (username := entry.data.get(CONF_USERNAME)) and (
        password := entry.data.get(CONF_PASSWORD)
    ):
        try:
            await box.authenticate(username=username, password=password)
        except SFRBoxAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_credentials",
            ) from err
        except SFRBoxError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(err)},
            ) from err
        platforms = PLATFORMS_WITH_AUTH

    data = SFRRuntimeData(
        box=box,
        dsl=SFRDataUpdateCoordinator(
            hass, entry, box, "dsl", lambda b: b.dsl_get_info()
        ),
        ftth=SFRDataUpdateCoordinator(
            hass, entry, box, "ftth", lambda b: b.ftth_get_info()
        ),
        system=SFRDataUpdateCoordinator(
            hass, entry, box, "system", lambda b: b.system_get_info()
        ),
        wan=SFRDataUpdateCoordinator(
            hass, entry, box, "wan", lambda b: b.wan_get_info()
        ),
    )
    # Preload system information
    await data.system.async_config_entry_first_refresh()
    system_info = data.system.data
    if TYPE_CHECKING:
        assert system_info is not None

    # Preload other coordinators (based on net infrastructure)
    tasks = [data.wan.async_config_entry_first_refresh()]
    if (net_infra := system_info.net_infra) == "adsl":
        tasks.append(data.dsl.async_config_entry_first_refresh())
    elif net_infra == "ftth":
        tasks.append(data.ftth.async_config_entry_first_refresh())
    await asyncio.gather(*tasks)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, system_info.mac_addr)},
        identifiers={(DOMAIN, system_info.mac_addr)},
        name="SFR Box",
        model=None,
        model_id=system_info.product_id,
        sw_version=system_info.version_mainfirmware,
        configuration_url=f"http://{entry.data[CONF_HOST]}",
    )

    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SFRConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.data.get(CONF_USERNAME) and entry.data.get(CONF_PASSWORD):
        return await hass.config_entries.async_unload_platforms(
            entry, PLATFORMS_WITH_AUTH
        )
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
