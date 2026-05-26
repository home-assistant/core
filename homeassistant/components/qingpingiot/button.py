"""Support for Qingping IoT button entities."""

import json
import logging

from homeassistant.components import mqtt
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_MODEL, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MODELS, DOMAIN, MQTT_TOPIC_PREFIX, TLV_MODELS, Capability
from .coordinator import QingpingCoordinator
from .tlv import tlv_encode

_LOGGER = logging.getLogger(__name__)

# Capability -> button config: (translation_key, tlv_key, tlv_value)
CAPABILITY_BUTTON_MAP: dict[Capability, tuple[str, int, int]] = {
    Capability.CO2_CALIBRATION: ("co2_calibration", 0x41, 1),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Qingping button entities from a config entry."""
    mac = config_entry.data[CONF_MAC]
    model = config_entry.data[CONF_MODEL]
    coordinator: QingpingCoordinator = config_entry.runtime_data.coordinator

    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, mac)},
        "name": config_entry.title,
        "manufacturer": "Qingping",
        "model": model,
    }

    model_info = DEVICE_MODELS.get(model)
    if not model_info:
        async_add_entities([])
        return

    entities: list[ButtonEntity] = []

    for cap in model_info["capabilities"]:
        if cap not in CAPABILITY_BUTTON_MAP:
            continue
        translation_key, tlv_key, tlv_value = CAPABILITY_BUTTON_MAP[cap]
        entities.append(
            QingpingButton(
                coordinator,
                config_entry,
                mac,
                model,
                device_info,
                translation_key,
                tlv_key,
                tlv_value,
            )
        )

    async_add_entities(entities)


class QingpingButton(CoordinatorEntity, ButtonEntity):
    """Button entity, sends one-shot command via TLV or JSON protocol."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: QingpingCoordinator,
        config_entry: ConfigEntry,
        mac: str,
        model: str,
        device_info: DeviceInfo,
        translation_key: str,
        tlv_key: int,
        tlv_value: int,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._mac = mac
        self._model = model
        self._is_tlv = model in TLV_MODELS
        self._tlv_key = tlv_key
        self._tlv_value = tlv_value
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{mac}_{translation_key}"
        self._attr_device_info = device_info
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Send the button press command to the device."""
        topic = f"{MQTT_TOPIC_PREFIX}/{self._mac}/down"
        if self._is_tlv:
            packets = {self._tlv_key: bytes([self._tlv_value])}
            payload: bytes | str = tlv_encode(0x32, packets)
            await mqtt.async_publish(self.hass, topic, payload)
            _LOGGER.debug(
                "[%s] Sent TLV button %s (key=0x%02X, val=%d)",
                self._mac,
                self._attr_translation_key,
                self._tlv_key,
                self._tlv_value,
            )
        else:
            # JSON devices use type 29 for CO2 calibration
            payload = json.dumps({"type": "29"})
            await mqtt.async_publish(self.hass, topic, payload)
            _LOGGER.debug(
                "[%s] Sent JSON button %s (type=29)",
                self._mac,
                self._attr_translation_key,
            )
