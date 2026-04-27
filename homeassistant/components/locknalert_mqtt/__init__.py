"""LocknAlert integration setup."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .bridge_api import LocknAlertBridgeApi
from .const import (
    CONF_BRIDGE_SERIAL,
    CONF_LocknAlertMQTT,
    CONF_PREFIX,
    CONF_TLS_REQUIRED,
    CONF_VERIFY_SSL,
    PLATFORMS,
)
from .coordinator import LocknAlertCoordinator
from .mqtt_client import LocknAlertMqttClient


@dataclass(slots=True)
class LocknAlertRuntimeData:
    """Runtime objects stored on the config entry."""

    coordinator: LocknAlertCoordinator
    api: LocknAlertBridgeApi
    mqtt_client: LocknAlertMqttClient


type LocknAlertConfigEntry = ConfigEntry[LocknAlertRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: LocknAlertConfigEntry) -> bool:
    """Set up LocknAlert from a config entry."""
    data = entry.data
    mqtt = data[CONF_LocknAlertMQTT]
    bridge_serial = str(data[CONF_BRIDGE_SERIAL])

    coordinator = LocknAlertCoordinator()
    api = LocknAlertBridgeApi(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        verify_ssl=data.get(CONF_VERIFY_SSL, False),
    )
    mqtt_client = LocknAlertMqttClient(
        coordinator=coordinator,
        bridge_id=bridge_serial,
        prefix=mqtt.get(CONF_PREFIX, "locknalert"),
        host=mqtt[CONF_HOST],
        port=mqtt[CONF_PORT],
        username=mqtt["username"],
        password=mqtt["password"],
        tls_required=mqtt.get(CONF_TLS_REQUIRED, True),
    )

    try:
        await mqtt_client.async_start()
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to LocknAlertLocknAlertMQTT broker: {err}") from err

    entry.runtime_data = LocknAlertRuntimeData(coordinator=coordinator, api=api, mqtt_client=mqtt_client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LocknAlertConfigEntry) -> bool:
    """Unload LocknAlert config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.mqtt_client.async_stop()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: LocknAlertConfigEntry) -> bool:
    """Handle future migrations for stored bootstrap schema."""
    if entry.version == 1:
        return True
    return False
