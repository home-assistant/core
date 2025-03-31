"""SFR Box."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sfrbox_api.bridge import SFRBox
from sfrbox_api.exceptions import SFRBoxAuthenticationError, SFRBoxError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, PLATFORMS, PLATFORMS_WITH_AUTH
from .coordinator import SFRDataUpdateCoordinator
from .models import DomainData


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SFR box as config entry."""
    box = SFRBox(ip=entry.data[CONF_HOST], client=get_async_client(hass))
    platforms = PLATFORMS
    if (username := entry.data.get(CONF_USERNAME)) and (
        password := entry.data.get(CONF_PASSWORD)
    ):
        try:
            await box.authenticate(username=username, password=password)
        except SFRBoxAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except SFRBoxError as err:
            raise ConfigEntryNotReady from err
        platforms = PLATFORMS_WITH_AUTH

    data = DomainData(
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

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, system_info.mac_addr)},
        name="SFR Box",
        model=system_info.product_id,
        model_id=system_info.product_id,
        sw_version=system_info.version_mainfirmware,
        configuration_url=f"http://{entry.data[CONF_HOST]}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
