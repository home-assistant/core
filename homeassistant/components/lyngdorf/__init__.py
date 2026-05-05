"""The Lyngdorf integration."""

from __future__ import annotations

from lyngdorf.device import async_create_receiver, lookup_receiver_model

from homeassistant.const import CONF_HOST, CONF_MODEL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)

from .const import CONF_SERIAL_NUMBER, DOMAIN, PLATFORMS
from .models import LyngdorfConfigEntry, LyngdorfRuntimeData


def _serial_as_mac(serial: str | None) -> str | None:
    """Return a normalized MAC if the serial is one, otherwise None.

    Lyngdorf reports the device MAC in the UPnP serialNumber field, but this is
    not formally guaranteed — fall back gracefully if the value is not a MAC.
    """
    if not serial:
        return None
    cleaned = serial.replace(":", "").replace("-", "").replace(".", "")
    if len(cleaned) != 12 or not all(c in "0123456789abcdefABCDEF" for c in cleaned):
        return None
    return format_mac(cleaned)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: LyngdorfConfigEntry
) -> bool:
    """Set up Lyngdorf from a config entry."""
    lyngdorf_model = lookup_receiver_model(config_entry.data[CONF_MODEL])

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
    serial = config_entry.data.get(CONF_SERIAL_NUMBER)
    mac = _serial_as_mac(serial)
    connections = {(CONNECTION_NETWORK_MAC, mac)} if mac else set()
    manufacturer = lyngdorf_model.manufacturer if lyngdorf_model else "Lyngdorf"
    model = (
        lyngdorf_model.model_name if lyngdorf_model else config_entry.data[CONF_MODEL]
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.unique_id)},
        connections=connections,
        manufacturer=manufacturer,
        serial_number=serial,
        model=model,
    )

    zone_b_device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{config_entry.unique_id}_zone_b")},
        manufacturer=manufacturer,
        serial_number=serial,
        model=model,
        translation_key="zone_b",
        translation_placeholders={"device_name": config_entry.title},
        via_device=(DOMAIN, config_entry.unique_id),
    )

    config_entry.runtime_data = LyngdorfRuntimeData(
        receiver=receiver,
        device_info=device_info,
        zone_b_device_info=zone_b_device_info,
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
