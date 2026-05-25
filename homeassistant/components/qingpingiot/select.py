"""Support for Qingping IoT select entities."""

import json
import logging

from homeassistant.components import mqtt
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ETVOC_UNIT,
    CONF_TEMPERATURE_UNIT,
    DEVICE_MODELS,
    DOMAIN,
    MQTT_TOPIC_PREFIX,
    TLV_MODELS,
    Capability,
)
from .coordinator import QingpingCoordinator
from .tlv import tlv_encode

_LOGGER = logging.getLogger(__name__)

ETVOC_UNIT_OPTIONS = ["index", "ppb", "mg_m3"]
TEMPERATURE_UNIT_OPTIONS = ["celsius", "fahrenheit"]


# Capability -> (conf_key, translation_key, options, entity_class)
CAPABILITY_SELECT_MAP: dict[Capability, tuple[str, str, list[str], type]] = {
    Capability.ETVOC: (CONF_ETVOC_UNIT, "etvoc_unit", ETVOC_UNIT_OPTIONS, "etvoc"),
    Capability.TEMPERATURE_UNIT: (
        CONF_TEMPERATURE_UNIT,
        "temperature_unit",
        TEMPERATURE_UNIT_OPTIONS,
        "temperature",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qingping select entities from a config entry."""
    mac = config_entry.data[CONF_MAC]
    model = config_entry.data[CONF_MODEL]
    coordinator: QingpingCoordinator = config_entry.runtime_data.coordinator

    device_info = {
        "identifiers": {(DOMAIN, mac)},
        "name": config_entry.data[CONF_NAME],
        "manufacturer": "Qingping",
        "model": model,
    }

    model_info = DEVICE_MODELS.get(model)
    if not model_info:
        async_add_entities([])
        return

    entities: list[SelectEntity] = []

    for cap in model_info["capabilities"]:
        if cap not in CAPABILITY_SELECT_MAP:
            continue
        conf_key, translation_key, options, entity_type = CAPABILITY_SELECT_MAP[cap]
        if entity_type == "etvoc":
            entities.append(
                QingpingTLVeTVOCUnitSelect(
                    coordinator,
                    config_entry,
                    mac,
                    device_info,
                    conf_key,
                    translation_key,
                    options,
                )
            )
        elif entity_type == "temperature":
            entities.append(
                QingpingTLVTemperatureUnitSelect(
                    coordinator,
                    config_entry,
                    mac,
                    model,
                    device_info,
                    conf_key,
                    translation_key,
                    options,
                )
            )

    async_add_entities(entities)


class QingpingTLVeTVOCUnitSelect(CoordinatorEntity, SelectEntity):
    """Select entity for eTVOC unit on TLV devices, sends command to device."""

    _attr_has_entity_name = True

    # TLV KEY 0x62: 1=index, 3=mg/m³, 4=ppb
    _TLV_UNIT_MAP = {"index": 1, "mg_m3": 3, "ppb": 4}

    def __init__(
        self,
        coordinator: QingpingCoordinator,
        config_entry: ConfigEntry,
        mac: str,
        device_info: dict,
        conf_key: str,
        translation_key: str,
        options: list[str],
    ) -> None:
        """Initialize the eTVOC unit select entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._mac = mac
        self._conf_key = conf_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{mac}_{conf_key}"
        self._attr_device_info = device_info
        self._attr_options = options
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:air-filter"

    @property
    def current_option(self) -> str | None:
        """Return the current eTVOC unit."""
        return self.coordinator.data.get(self._conf_key, self._attr_options[0])

    async def async_select_option(self, option: str) -> None:
        """Select a new eTVOC unit."""
        self.coordinator.data[self._conf_key] = option
        self.async_write_ha_state()

        new_data = dict(self._config_entry.data)
        new_data[self._conf_key] = option
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)

        await self.coordinator.async_request_refresh()

        tlv_value = self._TLV_UNIT_MAP.get(option, 1)
        packets = {0x62: bytes([tlv_value])}
        payload = tlv_encode(0x32, packets)
        topic = f"{MQTT_TOPIC_PREFIX}/{self._mac}/down"
        await mqtt.async_publish(self.hass, topic, payload)
        _LOGGER.debug(
            "[%s] Sent TLV %s=%s (key=0x62, val=%d)",
            self._mac,
            self._conf_key,
            option,
            tlv_value,
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._conf_key not in self.coordinator.data:
            self.coordinator.data[self._conf_key] = self._config_entry.data.get(
                self._conf_key, self._attr_options[0]
            )
        self.async_write_ha_state()


class QingpingTLVTemperatureUnitSelect(CoordinatorEntity, SelectEntity):
    """Select entity for temperature unit, supports both TLV and JSON devices."""

    _attr_has_entity_name = True

    # TLV KEY 0x19: 0x00=Celsius, 0x01=Fahrenheit
    _TLV_UNIT_MAP = {"celsius": 0x00, "fahrenheit": 0x01}
    # JSON: "C" or "F"
    _JSON_UNIT_MAP = {"celsius": "C", "fahrenheit": "F"}

    def __init__(
        self,
        coordinator: QingpingCoordinator,
        config_entry: ConfigEntry,
        mac: str,
        model: str,
        device_info: dict,
        conf_key: str,
        translation_key: str,
        options: list[str],
    ) -> None:
        """Initialize the temperature unit select entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._mac = mac
        self._model = model
        self._is_tlv = model in TLV_MODELS
        self._conf_key = conf_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{mac}_{conf_key}"
        self._attr_device_info = device_info
        self._attr_options = options
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:thermometer"

    @property
    def current_option(self) -> str | None:
        """Return the current temperature unit."""
        return self.coordinator.data.get(self._conf_key, self._attr_options[0])

    async def async_select_option(self, option: str) -> None:
        """Select a new temperature unit."""
        self.coordinator.data[self._conf_key] = option
        self.async_write_ha_state()

        new_data = dict(self._config_entry.data)
        new_data[self._conf_key] = option
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)

        await self.coordinator.async_request_refresh()

        topic = f"{MQTT_TOPIC_PREFIX}/{self._mac}/down"

        if self._is_tlv:
            tlv_value = self._TLV_UNIT_MAP.get(option, 0x00)
            packets = {0x19: bytes([tlv_value])}
            payload = tlv_encode(0x32, packets)
            _LOGGER.debug(
                "[%s] Sent TLV %s=%s (key=0x19, val=%d)",
                self._mac,
                self._conf_key,
                option,
                tlv_value,
            )
        else:
            json_value = self._JSON_UNIT_MAP.get(option, "C")
            payload = json.dumps(
                {"type": "17", "setting": {"temperature_unit": json_value}}
            )
            _LOGGER.debug("[%s] Sent JSON %s=%s", self._mac, self._conf_key, json_value)

        await mqtt.async_publish(self.hass, topic, payload)

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._conf_key not in self.coordinator.data:
            self.coordinator.data[self._conf_key] = self._config_entry.data.get(
                self._conf_key, self._attr_options[0]
            )
        self.async_write_ha_state()
