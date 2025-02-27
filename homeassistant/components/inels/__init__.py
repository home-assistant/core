"""The iNELS integration."""

from __future__ import annotations

from dataclasses import dataclass

from inelsmqtt import InelsMqtt
from inelsmqtt.devices import Device
from inelsmqtt.discovery import InelsDiscovery
from paho.mqtt import MQTTException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import LOGGER

type InelsConfigEntry = ConfigEntry[InelsData]

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
]


@dataclass
class InelsData:
    """Represents the data structure for INELS runtime data."""

    mqtt: InelsMqtt
    devices: list[Device]


def inels_discovery(mqtt: InelsMqtt) -> list[Device]:
    """Discover iNELS devices."""

    try:
        i_disc = InelsDiscovery(mqtt)
        devices: list[Device] = i_disc.discovery()
    except (
        MQTTException,
        TimeoutError,
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
    ) as exc:
        LOGGER.error("Discovery error %s, reason %s", exc.__class__.__name__, exc)
        mqtt.close()
        raise ConfigEntryNotReady from exc
    except Exception as exc:
        LOGGER.error(
            "Discovery unexpected error %s, reason %s", exc.__class__.__name__, exc
        )
        mqtt.close()
        raise ConfigEntryNotReady from exc
    else:
        return devices


async def async_setup_entry(hass: HomeAssistant, entry: InelsConfigEntry) -> bool:
    """Set up iNELS from a config entry."""

    mqtt = InelsMqtt(entry.data)

    def connect_and_discover_devices() -> list[Device] | None:
        """Test connection and discover devices."""
        conn_result = mqtt.test_connection()
        if isinstance(conn_result, int):  # None -> no error, int -> error code
            mqtt.close()
            if conn_result in (4, 5):
                raise ConfigEntryAuthFailed("Invalid authentication")
            if conn_result == 3:
                raise ConfigEntryNotReady("MQTT Broker is offline or cannot be reached")
            return None
        return inels_discovery(mqtt)

    # Raising errors signals to Home Assistant that the setup should be retried later.
    # It is better to retry the entire setup than to recover from errors.
    devices = await hass.async_add_executor_job(connect_and_discover_devices)

    # Check for errors that were not explicitly raised
    if devices is None:
        return False

    # If no devices are discovered, continue with the setup
    if not devices:
        LOGGER.warning("No devices discovered")

    entry.runtime_data = InelsData(mqtt=mqtt, devices=devices)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: InelsConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.mqtt.unsubscribe_listeners()
    entry.runtime_data.mqtt.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
