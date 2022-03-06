"""Support for monitoring the Deluge BitTorrent client API."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    DATA_RATE_KILOBYTES_PER_SECOND,
    STATE_IDLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import DelugeEntity
from .const import DEFAULT_NAME, DEFAULT_RPC_PORT, DOMAIN
from .coordinator import DelugeDataUpdateCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="current_status",
        name="Status",
    ),
    SensorEntityDescription(
        key="download_speed",
        name="Down Speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="upload_speed",
        name="Up Speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

# Deprecated in Home Assistant 2022.3
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_RPC_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: entity_platform.AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Deluge sensor component."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up the Deluge sensor."""
    async_add_entities(
        DelugeSensor(hass.data[DOMAIN][entry.entry_id], description)
        for description in SENSOR_TYPES
    )


class DelugeSensor(DelugeEntity, SensorEntity):
    """Representation of a Deluge sensor."""

    coordinator: DelugeDataUpdateCoordinator

    def __init__(
        self,
        coordinator: DelugeDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.config_entry.title} {description.name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}/{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.coordinator.data:
            data = self.coordinator.data[Platform.SENSOR]
            upload = data[b"upload_rate"] - data[b"dht_upload_rate"]
            download = data[b"download_rate"] - data[b"dht_download_rate"]
            if self.entity_description.key == "current_status":
                if data:
                    if upload > 0 and download > 0:
                        return "Up/Down"
                    if upload > 0 and download == 0:
                        return "Seeding"
                    if upload == 0 and download > 0:
                        return "Downloading"
                    return STATE_IDLE

            if data:
                if self.entity_description.key == "download_speed":
                    kb_spd = float(download)
                    kb_spd = kb_spd / 1024
                    return round(kb_spd, 2 if kb_spd < 0.1 else 1)
                if self.entity_description.key == "upload_speed":
                    kb_spd = float(upload)
                    kb_spd = kb_spd / 1024
                    return round(kb_spd, 2 if kb_spd < 0.1 else 1)
        return None
