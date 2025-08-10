"""Support for Huawei LTE binary sensors."""

from __future__ import annotations

import logging
from typing import Any

from huawei_lte_api.enums.cradle import ConnectionStatusEnum

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    KEY_MONITORING_CHECK_NOTIFICATIONS,
    KEY_MONITORING_STATUS,
    KEY_WLAN_WIFI_FEATURE_SWITCH,
)
from .entity import HuaweiLteBaseEntityWithDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up from config entry."""
    router = hass.data[DOMAIN].routers[config_entry.entry_id]
    entities: list[Entity] = []

    if router.data.get(KEY_MONITORING_STATUS):
        entities.append(HuaweiLteMobileConnectionBinarySensor(router))
        entities.append(HuaweiLteWifiStatusBinarySensor(router))
        entities.append(HuaweiLteWifi24ghzStatusBinarySensor(router))
        entities.append(HuaweiLteWifi5ghzStatusBinarySensor(router))

    if router.data.get(KEY_MONITORING_CHECK_NOTIFICATIONS):
        entities.append(HuaweiLteSmsStorageFullBinarySensor(router))

    async_add_entities(entities, True)


class HuaweiLteBaseBinarySensor(HuaweiLteBaseEntityWithDevice, BinarySensorEntity):
    """Huawei LTE binary sensor device base class."""

    _attr_entity_registry_enabled_default = False

    key: str
    item: str
    _raw_state: str | None = None

    @property
    def _device_unique_id(self) -> str:
        return f"{self.key}.{self.item}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to needed data on add."""
        await super().async_added_to_hass()
        self.router.subscriptions[self.key].append(
            f"{BINARY_SENSOR_DOMAIN}/{self.item}"
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from needed data on remove."""
        await super().async_will_remove_from_hass()
        self.router.subscriptions[self.key].remove(
            f"{BINARY_SENSOR_DOMAIN}/{self.item}"
        )

    async def async_update(self) -> None:
        """Update state."""
        try:
            value = self.router.data[self.key][self.item]
        except KeyError:
            value = None
            _LOGGER.debug("%s[%s] not in data", self.key, self.item)
        if value is None:
            self._raw_state = value
            self._available = False
        else:
            self._raw_state = str(value)
            self._available = True


CONNECTION_STATE_ATTRIBUTES = {
    str(ConnectionStatusEnum.CONNECTING): "Connecting",
    str(ConnectionStatusEnum.DISCONNECTING): "Disconnecting",
    str(ConnectionStatusEnum.CONNECT_FAILED): "Connect failed",
    str(ConnectionStatusEnum.CONNECT_STATUS_NULL): "Status not available",
    str(ConnectionStatusEnum.CONNECT_STATUS_ERROR): "Status error",
}


class HuaweiLteMobileConnectionBinarySensor(HuaweiLteBaseBinarySensor):
    """Huawei LTE mobile connection binary sensor."""

    _attr_translation_key = "mobile_connection"
    _attr_entity_registry_enabled_default = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    key = KEY_MONITORING_STATUS
    item = "ConnectionStatus"

    @property
    def is_on(self) -> bool:
        """Return whether the binary sensor is on."""
        return bool(
            self._raw_state
            and int(self._raw_state)
            in (ConnectionStatusEnum.CONNECTED, ConnectionStatusEnum.DISCONNECTING)
        )

    @property
    def assumed_state(self) -> bool:
        """Return True if real state is assumed, not known."""
        return not self._raw_state or int(self._raw_state) not in (
            ConnectionStatusEnum.CONNECT_FAILED,
            ConnectionStatusEnum.CONNECTED,
            ConnectionStatusEnum.DISCONNECTED,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Get additional attributes related to connection status."""
        attributes = {}
        if self._raw_state in CONNECTION_STATE_ATTRIBUTES:
            attributes["additional_state"] = CONNECTION_STATE_ATTRIBUTES[
                self._raw_state
            ]
        return attributes


class HuaweiLteBaseWifiStatusBinarySensor(HuaweiLteBaseBinarySensor):
    """Huawei LTE WiFi status binary sensor base class."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return whether the binary sensor is on."""
        return self._raw_state is not None and int(self._raw_state) == 1

    @property
    def assumed_state(self) -> bool:
        """Return True if real state is assumed, not known."""
        return self._raw_state is None


class HuaweiLteWifiStatusBinarySensor(HuaweiLteBaseWifiStatusBinarySensor):
    """Huawei LTE WiFi status binary sensor."""

    _attr_translation_key: str = "wifi_status"

    key = KEY_MONITORING_STATUS
    item = "WifiStatus"


class HuaweiLteWifi24ghzStatusBinarySensor(HuaweiLteBaseWifiStatusBinarySensor):
    """Huawei LTE 2.4GHz WiFi status binary sensor."""

    _attr_translation_key: str = "24ghz_wifi_status"

    key = KEY_WLAN_WIFI_FEATURE_SWITCH
    item = "wifi24g_switch_enable"


class HuaweiLteWifi5ghzStatusBinarySensor(HuaweiLteBaseWifiStatusBinarySensor):
    """Huawei LTE 5GHz WiFi status binary sensor."""

    _attr_translation_key: str = "5ghz_wifi_status"

    key = KEY_WLAN_WIFI_FEATURE_SWITCH
    item = "wifi5g_enabled"


class HuaweiLteSmsStorageFullBinarySensor(HuaweiLteBaseBinarySensor):
    """Huawei LTE SMS storage full binary sensor."""

    _attr_translation_key: str = "sms_storage_full"

    key = KEY_MONITORING_CHECK_NOTIFICATIONS
    item = "SmsStorageFull"

    @property
    def is_on(self) -> bool:
        """Return whether the binary sensor is on."""
        return self._raw_state is not None and int(self._raw_state) != 0

    @property
    def assumed_state(self) -> bool:
        """Return True if real state is assumed, not known."""
        return self._raw_state is None
