"""The my-PV integration for Home Assistant."""

from __future__ import annotations

from datetime import timedelta
import logging

from mypv import MyPVCloudDevice, MyPVLocalDevice
from mypv.exceptions import MyPVAuthenticationError, MyPVConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .const import CONF_SERIAL_NUMBER, CONF_TYPE_CLOUD, CONF_TYPE_LOCAL, DOMAIN
from .coordinator import MyPVCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.WATER_HEATER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up my-PV from a config entry."""

    conf_type: str = entry.data[CONF_TYPE]

    device = None
    update_interval = timedelta(seconds=5)
    if conf_type == CONF_TYPE_LOCAL:
        password = entry.data.get(CONF_PASSWORD)
        device = await MyPVLocalDevice(entry.data[CONF_HOST], password)
    elif conf_type == CONF_TYPE_CLOUD:
        device = await MyPVCloudDevice(
            entry.data[CONF_SERIAL_NUMBER], entry.data[CONF_TOKEN]
        )
        update_interval = timedelta(seconds=30)
    else:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="config_type_not_supported",
            translation_placeholders={"config_type": conf_type},
        )

    try:
        if not await device.connect():
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="could_not_connect",
                translation_placeholders={"uri": device.uri},
            )
    except MyPVAuthenticationError as exc:
        raise ConfigEntryAuthFailed from exc
    except MyPVConnectionError as exc:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="could_not_connect",
            translation_placeholders={"uri": device.uri},
        ) from exc

    # Setup coordinator
    coordinator = MyPVCoordinator(hass, entry, device, update_interval)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: MyPVCoordinator = entry.runtime_data
    await coordinator.async_disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
