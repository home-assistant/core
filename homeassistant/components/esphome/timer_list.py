"""Timer list for ESPHome voice satellites."""

from homeassistant.components.timer_list import InMemoryTimerListEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entry_data import ESPHomeConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the timer list for a voice-capable ESPHome device."""
    entry_data = entry.runtime_data
    device_info = entry_data.device_info
    assert device_info is not None
    if not device_info.voice_assistant_feature_flags_compat(entry_data.api_version):
        return

    mac = device_info.mac_address
    async_add_entities(
        [
            InMemoryTimerListEntity(
                name="Timers",
                unique_id=f"{mac}-timer_list",
                device_info=DeviceInfo(connections={(dr.CONNECTION_NETWORK_MAC, mac)}),
            )
        ]
    )
