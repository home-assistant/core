"""Support for Qingping IoT switch entities."""

import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_MODEL, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MODELS, DOMAIN, MQTT_TOPIC_PREFIX, TLV_MODELS, Capability
from .coordinator import QingpingCoordinator
from .tlv import tlv_encode

_LOGGER = logging.getLogger(__name__)

# Capability -> switch config: (translation_key, tlv_key, default)
CAPABILITY_SWITCH_MAP: dict[Capability, tuple[str, int, bool]] = {
    Capability.CO2_ASC: ("co2_asc", 0x40, True),
    Capability.LED_INDICATOR: ("led_indicator", 0x63, True),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Qingping switch entities from a config entry."""
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

    entities: list[SwitchEntity] = []

    for cap in model_info["capabilities"]:
        if cap not in CAPABILITY_SWITCH_MAP:
            continue
        translation_key, tlv_key, default = CAPABILITY_SWITCH_MAP[cap]
        entities.append(
            QingpingSwitch(
                coordinator,
                config_entry,
                mac,
                model,
                device_info,
                translation_key,
                tlv_key,
                default,
            )
        )

    async_add_entities(entities)


class QingpingSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity, sends command via TLV or JSON protocol."""

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
        default: bool = False,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._mac = mac
        self._model = model
        self._is_tlv = model in TLV_MODELS
        self._conf_key = translation_key
        self._tlv_key = tlv_key
        self._default = default
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{mac}_{translation_key}"
        self._attr_device_info = device_info
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        return self.coordinator.data.get(self._conf_key, self._default)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.coordinator.data[self._conf_key] = True
        self.async_write_ha_state()
        await self._send(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.coordinator.data[self._conf_key] = False
        self.async_write_ha_state()
        await self._send(0)

    async def _send(self, value: int) -> None:
        topic = f"{MQTT_TOPIC_PREFIX}/{self._mac}/down"
        if self._is_tlv:
            packets = {self._tlv_key: bytes([value])}
            payload: bytes | str = tlv_encode(0x32, packets)
            await mqtt.async_publish(self.hass, topic, payload)
            _LOGGER.debug(
                "[%s] Sent TLV %s=%d (key=0x%02X)",
                self._mac,
                self._conf_key,
                value,
                self._tlv_key,
            )
        else:
            payload = json.dumps({"type": "17", "setting": {self._conf_key: value}})
            await mqtt.async_publish(self.hass, topic, payload)
            _LOGGER.debug("[%s] Sent JSON %s=%d", self._mac, self._conf_key, value)

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._conf_key not in self.coordinator.data:
            self.coordinator.data[self._conf_key] = self._default
        self.async_write_ha_state()
