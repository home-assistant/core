"""Common code for victron_gx integration."""

from abc import abstractmethod
from typing import Any

from victron_mqtt import Device as VictronVenusDevice, Metric as VictronVenusMetric

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

# Entities that should be marked as diagnostic
ENTITIES_CATEGORY_DIAGNOSTIC = ["system_heartbeat"]
# Entities that should be disabled by default
ENTITIES_DISABLE_BY_DEFAULT = ["system_heartbeat"]


class VictronBaseEntity(Entity):
    """Implementation of a Victron GX base entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the entity."""
        self._device = device
        self._metric = metric
        self._attr_device_info = device_info
        self._attr_unique_id = metric.unique_id
        self._attr_suggested_display_precision = metric.precision
        self._attr_translation_key = metric.generic_short_id.replace("{", "").replace(
            "}", ""
        )
        self._attr_translation_placeholders = metric.key_values

        self._attr_entity_category = (
            EntityCategory.DIAGNOSTIC
            if metric.generic_short_id in ENTITIES_CATEGORY_DIAGNOSTIC
            else None
        )
        self._attr_entity_registry_enabled_default = (
            metric.generic_short_id not in ENTITIES_DISABLE_BY_DEFAULT
        )

    @callback
    @abstractmethod
    def _on_update_cb(self, value: Any) -> None:
        """Handle the metric update. Must be implemented by subclasses."""

    @callback
    def _on_update(self, _: VictronVenusMetric, value: Any) -> None:
        self._on_update_cb(value)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._metric.on_update = self._on_update

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        # Unregister update callback
        self._metric.on_update = None
        await super().async_will_remove_from_hass()
