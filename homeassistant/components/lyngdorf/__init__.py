"""The Lyngdorf integration."""

from __future__ import annotations

from lyngdorf.device import async_create_receiver, lookup_receiver_model

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
    lyngdorf_model = lookup_receiver_model(config_entry.data[CONF_MODEL])
    if not lyngdorf_model:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unsupported_model",
            translation_placeholders={"model": config_entry.data[CONF_MODEL]},
        )

    try:
        receiver = await async_create_receiver(
            config_entry.data[CONF_HOST], lyngdorf_model
        )
        await receiver.async_connect()
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_timeout",
            translation_placeholders={"host": config_entry.data[CONF_HOST]},
        ) from err
    except (ConnectionError, OSError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_connection_error",
            translation_placeholders={"host": config_entry.data[CONF_HOST]},
        ) from err

    assert config_entry.unique_id
    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.unique_id)},
        manufacturer=lyngdorf_model.manufacturer,
        serial_number=config_entry.data.get(CONF_SERIAL_NUMBER),
        model=lyngdorf_model.model_name,
    )

    config_entry.runtime_data = LyngdorfRuntimeData(
        receiver=receiver,
        device_info=device_info,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def _async_disconnect(event: Event) -> None:
        """Disconnect from receiver."""
        await receiver.async_disconnect()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect)
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: LyngdorfConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        await config_entry.runtime_data.receiver.async_disconnect()
    return unload_ok
