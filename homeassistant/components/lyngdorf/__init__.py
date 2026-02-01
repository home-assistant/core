"""The Lyngdorf integration."""

from __future__ import annotations

from contextlib import suppress

from lyngdorf.const import LyngdorfModel
from lyngdorf.device import (
    async_create_receiver,
    async_find_receiver_model,
    lookup_receiver_model,
)

from homeassistant.const import CONF_HOST, CONF_MODEL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_SERIAL_NUMBER, DOMAIN, PLATFORMS
from .models import LyngdorfConfigEntry, LyngdorfRuntimeData


async def async_setup_entry(
    hass: HomeAssistant, config_entry: LyngdorfConfigEntry
) -> bool:
    """Set up Lyngdorf from a config entry."""
    lyngdorf_model: LyngdorfModel | None = lookup_receiver_model(
        config_entry.data[CONF_MODEL]
    )
    if not lyngdorf_model:
        try:
            lyngdorf_model = await async_find_receiver_model(
                config_entry.data[CONF_HOST]
            )
        except TimeoutError as err:
            raise ConfigEntryNotReady(
                f"Timeout finding receiver model at {config_entry.data[CONF_HOST]}"
            ) from err
        except (ConnectionError, OSError) as err:
            raise ConfigEntryNotReady(
                f"Failed to find receiver model at {config_entry.data[CONF_HOST]}"
            ) from err

    if not lyngdorf_model:
        raise ConfigEntryError(f"Unsupported model {config_entry.data[CONF_MODEL]}")

    try:
        receiver = await async_create_receiver(
            config_entry.data[CONF_HOST], lyngdorf_model
        )
        await receiver.async_connect()
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            f"Timeout connecting to {config_entry.data[CONF_HOST]}"
        ) from err
    except (ConnectionError, OSError) as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to {config_entry.data[CONF_HOST]}"
        ) from err

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        manufacturer=lyngdorf_model.manufacturer,
        name=config_entry.title,
        serial_number=config_entry.data[CONF_SERIAL_NUMBER],
        model=lyngdorf_model.model,
    )

    config_entry.runtime_data = LyngdorfRuntimeData(
        receiver=receiver,
        device_info=device_info,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def _async_disconnect(event: Event) -> None:
        """Disconnect from Telnet."""
        await receiver.async_disconnect()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect)
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: LyngdorfConfigEntry
) -> bool:
    """Unload a config entry."""
    with suppress(Exception):
        await config_entry.runtime_data.receiver.async_disconnect()

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
