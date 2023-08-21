"""Support for getting data from websites with scraping."""
from __future__ import annotations

import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import CONF_STATE_CLASS, SensorDeviceClass
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
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
    TEMPLATE_SENSOR_BASE_SCHEMA,
    ManualTriggerEntity,
    ManualTriggerSensorEntity,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_INDEX, CONF_SELECT, DOMAIN
from .coordinator import ScrapeCoordinator

_LOGGER = logging.getLogger(__name__)

TRIGGER_ENTITY_OPTIONS = (
    CONF_AVAILABILITY,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_PICTURE,
    CONF_UNIQUE_ID,
    CONF_STATE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)


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

        trigger_entity_config = {CONF_NAME: sensor_config[CONF_NAME]}
        for key in TRIGGER_ENTITY_OPTIONS:
            if key not in sensor_config:
                continue
            trigger_entity_config[key] = sensor_config[key]

        entities.append(
            ScrapeSensor(
                hass,
                coordinator,
                trigger_entity_config,
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

        trigger_entity_config = {CONF_NAME: name}
        for key in TRIGGER_ENTITY_OPTIONS:
            if key not in sensor_config:
                continue
            trigger_entity_config[key] = sensor_config[key]

        entities.append(
            ScrapeSensor(
                hass,
                coordinator,
                trigger_entity_config,
                sensor_config[CONF_SELECT],
                sensor_config.get(CONF_ATTRIBUTE),
                sensor_config[CONF_INDEX],
                value_template,
                False,
            )
        )

    async_add_entities(entities)


class ScrapeSensor(CoordinatorEntity[ScrapeCoordinator], ManualTriggerSensorEntity):
    """Representation of a web scrape sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ScrapeCoordinator,
        trigger_entity_config: ConfigType,
        select: str,
        attr: str | None,
        index: int,
        value_template: Template | None,
        yaml: bool,
    ) -> None:
        """Initialize a web scrape sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        ManualTriggerSensorEntity.__init__(self, hass, trigger_entity_config)
        self._select = select
        self._attr = attr
        self._index = index
        self._value_template = value_template
        self._attr_native_value = None
        if not yaml and (unique_id := trigger_entity_config.get(CONF_UNIQUE_ID)):
            self._attr_name = None
            self._attr_has_entity_name = True
            self._attr_device_info = DeviceInfo(
                entry_type=DeviceEntryType.SERVICE,
                identifiers={(DOMAIN, unique_id)},
                manufacturer="Scrape",
                name=self.name,
            )

    def _extract_value(self) -> Any:
        """Parse the html extraction in the executor."""
        raw_data = self.coordinator.data
        value: str | list[str] | None
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
