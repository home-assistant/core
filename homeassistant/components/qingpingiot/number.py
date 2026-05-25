"""Support for Qingping Device number entities."""

import json
import logging

from homeassistant.components import mqtt
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_CO2_OFFSET,
    CONF_HUMIDITY_OFFSET,
    CONF_REPORT_INTERVAL,
    CONF_TEMPERATURE_OFFSET,
    DEFAULT_OFFSET,
    DEVICE_MODELS,
    DOMAIN,
    MQTT_TOPIC_PREFIX,
    TLV_MODELS,
    Capability,
)
from .coordinator import QingpingCoordinator
from .tlv import int_to_bytes_little_endian, tlv_encode

_LOGGER = logging.getLogger(__name__)

# Offset definitions: (conf_key, translation_key, unit, tlv_key, min, max, step, json_setting_key)
OFFSET_DEFS = {
    Capability.TEMPERATURE: (
        CONF_TEMPERATURE_OFFSET,
        "temperature_offset",
        "°C",
        0x46,
        -10.0,
        10.0,
        0.1,
        "temperature_offset",
    ),
    Capability.HUMIDITY: (
        CONF_HUMIDITY_OFFSET,
        "humidity_offset",
        "%",
        0x48,
        -20.0,
        20.0,
        0.1,
        "humidity_offset",
    ),
    Capability.CO2: (
        CONF_CO2_OFFSET,
        "co2_offset",
        "ppm",
        0x45,
        -500,
        500,
        1,
        "co2_offset",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qingping number entities from a config entry."""
    mac = config_entry.data[CONF_MAC]
    name = config_entry.data[CONF_NAME]
    model = config_entry.data[CONF_MODEL]
    coordinator: QingpingCoordinator = config_entry.runtime_data.coordinator

    device_info = {
        "identifiers": {(DOMAIN, mac)},
        "name": name,
        "manufacturer": "Qingping",
        "model": model,
    }

    entities = [
        QingpingReportIntervalNumber(
            coordinator, config_entry, mac, model, device_info
        ),
    ]

    # Add offset entities based on model capabilities
    model_info = DEVICE_MODELS.get(model)
    if model_info:
        for cap in model_info["capabilities"]:
            if cap in OFFSET_DEFS:
                (
                    conf_key,
                    translation_key,
                    unit,
                    tlv_key,
                    min_v,
                    max_v,
                    step,
                    json_key,
                ) = OFFSET_DEFS[cap]
                # Skip noise offset for TLV devices (no TLV key)
                if model in TLV_MODELS and tlv_key is None:
                    continue
                entities.append(
                    QingpingOffsetNumber(
                        coordinator,
                        config_entry,
                        mac,
                        model,
                        device_info,
                        conf_key,
                        translation_key,
                        unit,
                        tlv_key,
                        json_key,
                        min_v,
                        max_v,
                        step,
                    )
                )

    async_add_entities(entities)


class QingpingReportIntervalNumber(CoordinatorEntity, NumberEntity):
    """Number entity for report interval, supports both TLV and JSON devices."""

    _attr_has_entity_name = True
    _attr_translation_key = "report_interval"

    def __init__(
        self,
        coordinator: QingpingCoordinator,
        config_entry: ConfigEntry,
        mac: str,
        model: str,
        device_info: dict,
    ) -> None:
        """Initialize the report interval number entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._mac = mac
        self._model = model
        self._is_tlv = model in TLV_MODELS

        ri_config = DEVICE_MODELS.get(model, {}).get("report_interval", {})
        self._ri_default = ri_config.get("default", 15)
        ri_unit = ri_config.get("unit", "min")

        self._attr_unique_id = f"{mac}_report_interval"
        self._attr_device_info = device_info
        self._attr_mode = NumberMode.BOX
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:clock-outline"

        self._attr_native_min_value = ri_config.get("min", 1)
        self._attr_native_max_value = 1440 if ri_unit == "min" else 86400
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = ri_unit

    @property
    def native_value(self) -> int:
        """Return the current report interval value."""
        return self.coordinator.data.get(
            CONF_REPORT_INTERVAL,
            self._config_entry.data.get(
                CONF_REPORT_INTERVAL,
                self._ri_default,
            ),
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the report interval value."""
        int_value = int(value)
        self.coordinator.data[CONF_REPORT_INTERVAL] = int_value
        self.async_write_ha_state()

        new_data = dict(self._config_entry.data)
        new_data[CONF_REPORT_INTERVAL] = int_value
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)

        topic = f"{MQTT_TOPIC_PREFIX}/{self._mac}/down"

        if self._is_tlv:
            sample_interval = int_value * 60
            packets = {
                0x04: int_to_bytes_little_endian(int_value, 2),
                0x05: int_to_bytes_little_endian(sample_interval, 2),
            }
            payload = tlv_encode(0x32, packets)
            _LOGGER.debug(
                "[%s] Sending TLV report_interval=%d min, sample_interval=%d s",
                self._mac,
                int_value,
                sample_interval,
            )
            await mqtt.async_publish(self.hass, topic, payload)
        else:
            payload = json.dumps(
                {
                    "type": "17",
                    "setting": {
                        "report_interval": int_value,
                        "collect_interval": int_value,
                    },
                }
            )
            _LOGGER.debug(
                "[%s] Sending JSON report_interval=%d s, collect_interval=%d s",
                self._mac,
                int_value,
                int_value,
            )
            await mqtt.async_publish(self.hass, topic, payload)

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        if CONF_REPORT_INTERVAL not in self.coordinator.data:
            self.coordinator.data[CONF_REPORT_INTERVAL] = self._config_entry.data.get(
                CONF_REPORT_INTERVAL,
                self._ri_default,
            )
        self.async_write_ha_state()


class QingpingOffsetNumber(CoordinatorEntity, NumberEntity):
    """Number entity for sensor offset, supports both TLV and JSON devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: QingpingCoordinator,
        config_entry: ConfigEntry,
        mac: str,
        model: str,
        device_info: dict,
        conf_key: str,
        translation_key: str,
        unit: str,
        tlv_key: int | None,
        json_key: str,
        min_value: float,
        max_value: float,
        step: float,
    ) -> None:
        """Initialize the offset number entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._mac = mac
        self._model = model
        self._conf_key = conf_key
        self._tlv_key = tlv_key
        self._json_key = json_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{mac}_{conf_key}"
        self._attr_device_info = device_info
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_mode = NumberMode.BOX
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> float:
        """Return the current offset value."""
        return self.coordinator.data.get(
            self._conf_key,
            self._config_entry.data.get(self._conf_key, DEFAULT_OFFSET),
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the offset value."""
        self.coordinator.data[self._conf_key] = value
        self.async_write_ha_state()

        new_data = dict(self._config_entry.data)
        new_data[self._conf_key] = value
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)

        topic = f"{MQTT_TOPIC_PREFIX}/{self._mac}/down"

        if self._model in TLV_MODELS:
            await self._send_tlv_offset(value, topic)
        else:
            await self._send_json_offset(value, topic)

    async def _send_tlv_offset(self, value: float, topic: str) -> None:
        """Send offset via TLV protocol."""
        if self._conf_key in (CONF_TEMPERATURE_OFFSET, CONF_HUMIDITY_OFFSET):
            device_value = int(value * 10)
        else:
            device_value = int(value)

        packets = {
            self._tlv_key: int_to_bytes_little_endian(device_value, 2, signed=True)
        }
        payload = tlv_encode(0x32, packets)
        _LOGGER.debug(
            "[%s] Sending TLV offset %s=%d", self._mac, self._conf_key, device_value
        )
        await mqtt.async_publish(self.hass, topic, payload)

    async def _send_json_offset(self, value: float, topic: str) -> None:
        """Send offset via JSON protocol."""
        if self._conf_key == CONF_TEMPERATURE_OFFSET:
            device_value = int(value * 100)
        elif self._conf_key == CONF_HUMIDITY_OFFSET:
            device_value = int(value * 10)
        else:
            device_value = int(value)

        payload = json.dumps(
            {
                "type": "17",
                "setting": {self._json_key: device_value},
            }
        )
        _LOGGER.debug(
            "[%s] Sending JSON offset %s=%d", self._mac, self._json_key, device_value
        )
        await mqtt.async_publish(self.hass, topic, payload)

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._conf_key not in self.coordinator.data:
            self.coordinator.data[self._conf_key] = self._config_entry.data.get(
                self._conf_key, DEFAULT_OFFSET
            )
        self.async_write_ha_state()
