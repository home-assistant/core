"""Support for getting data from websites with scraping."""
from __future__ import annotations

import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.components.sensor.helpers import async_parse_date_datetime
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
    TEMPLATE_SENSOR_BASE_SCHEMA,
    ManualTriggerEntity,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_INDEX, CONF_SELECT, DOMAIN
from .coordinator import ScrapeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Web scrape sensor."""
    discovery_info = cast(DiscoveryInfoType, discovery_info)
    coordinator: ScrapeCoordinator = discovery_info["coordinator"]
    sensors_config: list[ConfigType] = discovery_info["configs"]

    await coordinator.async_refresh()
    if coordinator.data is None:
        raise PlatformNotReady

    entities: list[ScrapeSensor] = []
    for sensor_config in sensors_config:
        value_template: Template | None = sensor_config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = hass

        trigger_entity_config = {
            CONF_NAME: sensor_config[CONF_NAME],
            CONF_DEVICE_CLASS: sensor_config.get(CONF_DEVICE_CLASS),
            CONF_UNIQUE_ID: sensor_config.get(CONF_UNIQUE_ID),
        }
        if available := sensor_config.get(CONF_AVAILABILITY):
            trigger_entity_config[CONF_AVAILABILITY] = available
        if icon := sensor_config.get(CONF_ICON):
            trigger_entity_config[CONF_ICON] = icon
        if picture := sensor_config.get(CONF_PICTURE):
            trigger_entity_config[CONF_PICTURE] = picture

        entities.append(
            ScrapeSensor(
                hass,
                coordinator,
                trigger_entity_config,
                sensor_config.get(CONF_UNIT_OF_MEASUREMENT),
                sensor_config.get(CONF_STATE_CLASS),
                sensor_config[CONF_SELECT],
                sensor_config.get(CONF_ATTRIBUTE),
                sensor_config[CONF_INDEX],
                value_template,
                True,
            )
        )

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Scrape sensor entry."""
    entities: list = []

    coordinator: ScrapeCoordinator = hass.data[DOMAIN][entry.entry_id]
    config = dict(entry.options)
    for sensor in config["sensor"]:
        sensor_config: ConfigType = vol.Schema(
            TEMPLATE_SENSOR_BASE_SCHEMA.schema, extra=vol.ALLOW_EXTRA
        )(sensor)

        name: str = sensor_config[CONF_NAME]
        value_string: str | None = sensor_config.get(CONF_VALUE_TEMPLATE)

        value_template: Template | None = (
            Template(value_string, hass) if value_string is not None else None
        )

        trigger_entity_config = {
            CONF_NAME: name,
            CONF_DEVICE_CLASS: sensor_config.get(CONF_DEVICE_CLASS),
            CONF_UNIQUE_ID: sensor_config[CONF_UNIQUE_ID],
        }

        entities.append(
            ScrapeSensor(
                hass,
                coordinator,
                trigger_entity_config,
                sensor_config.get(CONF_UNIT_OF_MEASUREMENT),
                sensor_config.get(CONF_STATE_CLASS),
                sensor_config[CONF_SELECT],
                sensor_config.get(CONF_ATTRIBUTE),
                sensor_config[CONF_INDEX],
                value_template,
                False,
            )
        )

    async_add_entities(entities)


class ScrapeSensor(
    CoordinatorEntity[ScrapeCoordinator], ManualTriggerEntity, SensorEntity
):
    """Representation of a web scrape sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ScrapeCoordinator,
        trigger_entity_config: ConfigType,
        unit_of_measurement: str | None,
        state_class: str | None,
        select: str,
        attr: str | None,
        index: int,
        value_template: Template | None,
        yaml: bool,
    ) -> None:
        """Initialize a web scrape sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        ManualTriggerEntity.__init__(self, hass, trigger_entity_config)
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_state_class = state_class
        self._select = select
        self._attr = attr
        self._index = index
        self._value_template = value_template
        self._attr_native_value = None
        if not yaml and trigger_entity_config.get(CONF_UNIQUE_ID):
            self._attr_name = None
            self._attr_has_entity_name = True
            self._attr_device_info = DeviceInfo(
                entry_type=DeviceEntryType.SERVICE,
                identifiers={(DOMAIN, trigger_entity_config[CONF_UNIQUE_ID])},
                manufacturer="Scrape",
                name=self.name,
            )

    def _extract_value(self) -> Any:
        """Parse the html extraction in the executor."""
        raw_data = self.coordinator.data
        try:
            if self._attr is not None:
                value = raw_data.select(self._select)[self._index][self._attr]
            else:
                tag = raw_data.select(self._select)[self._index]
                if tag.name in ("style", "script", "template"):
                    value = tag.string
                else:
                    value = tag.text
        except IndexError:
            _LOGGER.warning("Index '%s' not found in %s", self._index, self.entity_id)
            value = None
        except KeyError:
            _LOGGER.warning(
                "Attribute '%s' not found in %s", self._attr, self.entity_id
            )
            value = None
        _LOGGER.debug("Parsed value: %s", value)
        return value

    async def async_added_to_hass(self) -> None:
        """Ensure the data from the initial update is reflected in the state."""
        await ManualTriggerEntity.async_added_to_hass(self)
        # https://github.com/python/mypy/issues/15097
        await CoordinatorEntity.async_added_to_hass(self)  # type: ignore[arg-type]
        self._async_update_from_rest_data()

    def _async_update_from_rest_data(self) -> None:
        """Update state from the rest data."""
        value = self._extract_value()
        raw_value = value

        if (template := self._value_template) is not None:
            value = template.async_render_with_possible_json_value(value, None)

        if self.device_class not in {
            SensorDeviceClass.DATE,
            SensorDeviceClass.TIMESTAMP,
        }:
            self._attr_native_value = value
            self._process_manual_data(raw_value)
            return

        self._attr_native_value = async_parse_date_datetime(
            value, self.entity_id, self.device_class
        )
        self._process_manual_data(raw_value)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available1 = CoordinatorEntity.available.fget(self)  # type: ignore[attr-defined]
        available2 = ManualTriggerEntity.available.fget(self)  # type: ignore[attr-defined]
        return bool(available1 and available2)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_from_rest_data()
        super()._handle_coordinator_update()
