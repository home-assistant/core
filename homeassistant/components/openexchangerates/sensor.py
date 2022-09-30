"""Support for openexchangerates.org exchange rates service."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_BASE, CONF_NAME, CONF_QUOTE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_BASE, DOMAIN, LOGGER
from .coordinator import OpenexchangeratesCoordinator

ATTRIBUTION = "Data provided by openexchangerates.org"

DEFAULT_NAME = "Exchange Rate Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_QUOTE): cv.string,
        vol.Optional(CONF_BASE, default=DEFAULT_BASE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Open Exchange Rates sensor."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2022.11.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )

    LOGGER.warning(
        "Configuration of Open Exchange Rates integration in YAML is deprecated and "
        "will be removed in Home Assistant 2022.11.; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed from"
        " your configuration.yaml file"
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Open Exchange Rates sensor."""
    # Only YAML imported configs have name and quote in config entry data.
    name: str | None = config_entry.data.get(CONF_NAME)
    quote: str = config_entry.data.get(CONF_QUOTE, "EUR")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        OpenexchangeratesSensor(
            config_entry, coordinator, name, rate_quote, rate_quote == quote
        )
        for rate_quote in coordinator.data.rates
    )


class OpenexchangeratesSensor(
    CoordinatorEntity[OpenexchangeratesCoordinator], SensorEntity
):
    """Representation of an Open Exchange Rates sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: OpenexchangeratesCoordinator,
        name: str | None,
        quote: str,
        enabled: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Open Exchange Rates",
            name=f"Open Exchange Rates {coordinator.base}",
        )
        self._attr_entity_registry_enabled_default = enabled
        if name and enabled:
            # name is legacy imported from YAML config
            # this block can be removed when removing import from YAML
            self._attr_name = name
            self._attr_has_entity_name = False
        else:
            self._attr_name = quote
            self._attr_has_entity_name = True
        self._attr_native_unit_of_measurement = quote
        self._attr_unique_id = f"{config_entry.entry_id}_{quote}"
        self._quote = quote

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return round(self.coordinator.data.rates[self._quote], 4)
