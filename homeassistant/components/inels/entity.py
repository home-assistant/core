"""Base class for iNELS components."""

from __future__ import annotations

from inelsmqtt.devices import Device

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, LOGGER


class InelsBaseEntity(Entity):
    """Base iNELS device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: Device,
        key: str,
        index: int,
    ) -> None:
        """Init base entity."""
        self._device = device
        self._device_id = self._device.unique_id
        self._parent_id = self._device.parent_id
        self._attr_unique_id = self._device_id

        self._key = key
        self._index = index

        info = self._device.info()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.unique_id)},
            manufacturer=info.manufacturer,
            model=info.model_number,
            name=self._device.title,
            sw_version=info.sw_version,
            via_device=(DOMAIN, self._parent_id),
        )

        self._device.add_ha_callback(self.key, self.index, self._callback)

    async def async_added_to_hass(self) -> None:
        """Add subscription of the data listener."""
        self._device.mqtt.subscribe_listener(
            self._device.state_topic, self._device.unique_id, self._device.callback
        )

    def _callback(self) -> None:
        """Get data from broker into the HA."""
        if hasattr(self, "hass"):
            try:
                self.schedule_update_ha_state()
            except Exception as e:  # noqa: BLE001
                LOGGER.error(
                    "Error scheduling HA state update for DT_%s, %s, %s",
                    self._device.device_class,
                    self._device.info_serialized(),
                    e,
                )

    @property
    def should_poll(self) -> bool:
        """Need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return bool(self._device.is_available)

    @property
    def key(self) -> str:
        """Return the referenced variable to read from."""
        return self._key

    @property
    def index(self) -> int:
        """Return the index of the variable list to read from. '-1' for no index."""
        return self._index
