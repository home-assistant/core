"""The Nibe Heat Pump integration."""

from __future__ import annotations

from nibe.connection import Connection
from nibe.connection.modbus import Modbus
from nibe.connection.nibegw import NibeGW, ProductInfo
from nibe.heatpump import HeatPump, Model

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MODEL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_CONNECTION_TYPE_MODBUS,
    CONF_CONNECTION_TYPE_NIBEGW,
    CONF_LISTENING_PORT,
    CONF_MODBUS_UNIT,
    CONF_MODBUS_URL,
    CONF_REMOTE_READ_PORT,
    CONF_REMOTE_WRITE_PORT,
    CONF_WORD_SWAP,
    DOMAIN,
)
from .coordinator import CoilCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]
COIL_READ_RETRIES = 5


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nibe Heat Pump from a config entry."""

    heatpump = HeatPump(Model[entry.data[CONF_MODEL]])
    heatpump.word_swap = entry.data.get(CONF_WORD_SWAP, True)
    await heatpump.initialize()

    connection: Connection
    connection_type = entry.data[CONF_CONNECTION_TYPE]

    if connection_type == CONF_CONNECTION_TYPE_NIBEGW:
        connection = NibeGW(
            heatpump,
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_REMOTE_READ_PORT],
            entry.data[CONF_REMOTE_WRITE_PORT],
            listening_port=entry.data[CONF_LISTENING_PORT],
        )
    elif connection_type == CONF_CONNECTION_TYPE_MODBUS:
        connection = Modbus(
            heatpump, entry.data[CONF_MODBUS_URL], entry.data[CONF_MODBUS_UNIT]
        )
    else:
        raise HomeAssistantError(f"Connection type {connection_type} is not supported.")

    await connection.start()

    assert heatpump.model

    async def _async_stop(_):
        await connection.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )

    coordinator = CoilCoordinator(hass, heatpump, connection)

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = coordinator

    reg = dr.async_get(hass)
    device_entry = reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        manufacturer="NIBE Energy Systems",
        name=heatpump.model.name,
    )

    def _on_product_info(product_info: ProductInfo):
        reg.async_update_device(
            device_id=device_entry.id,
            model=product_info.model,
            sw_version=str(product_info.firmware_version),
        )

    if hasattr(connection, "PRODUCT_INFO_EVENT") and hasattr(connection, "subscribe"):
        connection.subscribe(connection.PRODUCT_INFO_EVENT, _on_product_info)
    else:
        reg.async_update_device(device_id=device_entry.id, model=heatpump.model.name)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Trigger a refresh again now that all platforms have registered
    hass.async_create_task(coordinator.async_refresh())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
