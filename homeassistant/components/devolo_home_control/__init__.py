"""The devolo_home_control integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from functools import partial
import logging
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

from .const import DOMAIN, PLATFORMS

type DevoloHomeControlConfigEntry = ConfigEntry[list[HomeControl]]


async def async_setup_entry(
    hass: HomeAssistant, entry: DevoloHomeControlConfigEntry
) -> bool:
    """Set up the devolo account from a config entry."""
    mydevolo = configure_mydevolo(entry.data)

    gateway_ids = await hass.async_add_executor_job(
        check_mydevolo_and_get_gateway_ids, mydevolo
    )

    def shutdown(event: Event) -> None:
        for gateway in entry.runtime_data:
            gateway.websocket_disconnect(
                f"websocket disconnect requested by {EVENT_HOMEASSISTANT_STOP}"
            )

    # Listen when EVENT_HOMEASSISTANT_STOP is fired
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)
    )

    zeroconf_instance = await zeroconf.async_get_instance(hass)
    entry.runtime_data = []
    offline_gateways = 0
    for gateway_id in gateway_ids:
        try:
            entry.runtime_data.append(
                await hass.async_add_executor_job(
                    partial(
                        HomeControl,
                        gateway_id=gateway_id,
                        mydevolo_instance=mydevolo,
                        zeroconf_instance=zeroconf_instance,
                    )
                )
            )
        except GatewayOfflineError:
            offline_gateways += 1
    if len(gateway_ids) == offline_gateways:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
            translation_placeholders={"gateway_id": ", ".join(gateway_ids)},
        )

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
    hass: HomeAssistant,
    config_entry: DevoloHomeControlConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    return True


def configure_mydevolo(conf: Mapping[str, Any]) -> Mydevolo:
    """Configure mydevolo."""
    mydevolo = Mydevolo()
    mydevolo.user = conf[CONF_USERNAME]
    mydevolo.password = conf[CONF_PASSWORD]

    # With gateways being accessible locally only, there is not need to warn here.
    logging.getLogger("Mydevolo").setLevel(logging.ERROR)

    return mydevolo


def check_mydevolo_and_get_gateway_ids(mydevolo: Mydevolo) -> list[str]:
    """Check if the credentials are valid and return user's gateway IDs as long as mydevolo is not in maintenance mode."""
    if not mydevolo.credentials_valid():
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        )
    if mydevolo.maintenance():
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="maintenance",
        )

    return mydevolo.get_gateway_ids()
