"""This integration provides support for Stookalert Binary Sensor."""
from __future__ import annotations

from datetime import timedelta

import stookalert
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_SAFETY,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_PROVINCE, DOMAIN, LOGGER, PROVINCES

DEFAULT_NAME = "Stookalert"
ATTRIBUTION = "Data provided by rivm.nl"
SCAN_INTERVAL = timedelta(minutes=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PROVINCE): vol.In(PROVINCES),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the Stookalert platform into a config entry."""
    LOGGER.warning(
        "Configuration of the Stookalert platform in YAML is deprecated and will be "
        "removed in Home Assistant 2022.1; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_PROVINCE: config[CONF_PROVINCE],
            },
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stookalert binary sensor from a config entry."""
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StookalertBinarySensor(client, entry)], update_before_add=True)


class StookalertBinarySensor(BinarySensorEntity):
    """Defines a Stookalert binary sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_device_class = DEVICE_CLASS_SAFETY

    def __init__(self, client: stookalert.stookalert, entry: ConfigEntry) -> None:
        """Initialize a Stookalert device."""
        self._client = client
        self._attr_name = f"Stookalert {entry.data[CONF_PROVINCE]}"
        self._attr_unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}")},
            name=entry.data[CONF_PROVINCE],
            manufacturer="RIVM",
            model="Stookalert",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.rivm.nl/stookalert",
        )

    def update(self) -> None:
        """Update the data from the Stookalert handler."""
        self._client.get_alerts()
        self._attr_is_on = self._client.state == 1
