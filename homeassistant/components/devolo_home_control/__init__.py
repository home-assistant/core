"""The devolo_home_control integration."""

from __future__ import annotations

import asyncio
from functools import partial
from types import MappingProxyType
from typing import Any

from devolo_home_control_api.exceptions.gateway import GatewayOfflineError
from devolo_home_control_api.homecontrol import HomeControl
from devolo_home_control_api.mydevolo import Mydevolo

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_MYDEVOLO, DEFAULT_MYDEVOLO, GATEWAY_SERIAL_PATTERN, PLATFORMS

type DevoloHomeControlConfigEntry = ConfigEntry[list[HomeControl]]


async def async_setup_entry(
    hass: HomeAssistant, entry: DevoloHomeControlConfigEntry
) -> bool:
    """Set up the devolo account from a config entry."""
    mydevolo = configure_mydevolo(entry.data)

    credentials_valid = await hass.async_add_executor_job(mydevolo.credentials_valid)

    if not credentials_valid:
        raise ConfigEntryAuthFailed

    if await hass.async_add_executor_job(mydevolo.maintenance):
        raise ConfigEntryNotReady

    gateway_ids = await hass.async_add_executor_job(mydevolo.get_gateway_ids)

    if entry.unique_id and GATEWAY_SERIAL_PATTERN.match(entry.unique_id):
        uuid = await hass.async_add_executor_job(mydevolo.uuid)
        hass.config_entries.async_update_entry(entry, unique_id=uuid)

    def shutdown(event: Event) -> None:
        for gateway in entry.runtime_data:
            gateway.websocket_disconnect(
                f"websocket disconnect requested by {EVENT_HOMEASSISTANT_STOP}"
            )

    # Listen when EVENT_HOMEASSISTANT_STOP is fired
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)
    )

    try:
        zeroconf_instance = await zeroconf.async_get_instance(hass)
        entry.runtime_data = []
        for gateway_id in gateway_ids:
            entry.runtime_data.append(
                await hass.async_add_executor_job(
                    partial(
                        HomeControl,
                        gateway_id=str(gateway_id),
                        mydevolo_instance=mydevolo,
                        zeroconf_instance=zeroconf_instance,
                    )
                )
            )
    except GatewayOfflineError as err:
        raise ConfigEntryNotReady from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DevoloHomeControlConfigEntry
) -> bool:
    """Unload a config entry."""
    unload = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await asyncio.gather(
        *(
            hass.async_add_executor_job(gateway.websocket_disconnect)
            for gateway in entry.runtime_data
        )
    )
    return unload


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


def configure_mydevolo(conf: dict[str, Any] | MappingProxyType[str, Any]) -> Mydevolo:
    """Configure mydevolo."""
    mydevolo = Mydevolo()
    mydevolo.user = conf[CONF_USERNAME]
    mydevolo.password = conf[CONF_PASSWORD]
    mydevolo.url = conf.get(CONF_MYDEVOLO, DEFAULT_MYDEVOLO)
    return mydevolo
