"""Base entity for entities in victron_gx integration."""

from abc import abstractmethod
from typing import Any, override

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricType,
)

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

# Entities that should be marked as diagnostic
ENTITIES_CATEGORY_DIAGNOSTIC = [
    "system_heartbeat",
    "platform_device_reboot",
    "solarcharger_device_off_reason",
]
# Entities that should be disabled by default
ENTITIES_DISABLE_BY_DEFAULT = [
    "system_heartbeat",
    "platform_device_reboot",
    "solarcharger_device_off_reason",
    # Per-tracker solar charger entities can multiply quickly on multi-tracker chargers.
    "solarcharger_tracker_{tracker}_power",
    "solarcharger_tracker_{tracker}_voltage",
    "solarcharger_tracker_{tracker}_current",
    "solarcharger_tracker_{tracker}_operation_mode",
    "solarcharger_tracker_{tracker}_name",
    "solarcharger_tracker_{tracker}_max_power_today",
    "solarcharger_tracker_{tracker}_max_voltage_today",
    "solarcharger_tracker_{tracker}_yield_today",
    # Per-MPPT multi-device entities have the same amplification problem.
    "multi_mppt_{mppt_id}_yield_today",
    "multi_mppt_{mppt_id}_yield_yesterday",
    "multi_mppt_{mpptnumber}_state",
    "multi_mppt_{mpptnumber}_power",
    "multi_mppt_{mpptnumber}_voltage",
    "multi_mppt_{mpptnumber}_current",
]
# Units that must be provided directly instead of via localization.
SPECIAL_NATIVE_UNITS = {"%", "Ah"}


class VictronBaseEntity(Entity):
    """Implementation of a Victron GX base entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Initialize the entity."""
        self._device = device
        self._metric = metric
        self._attr_device_info = device_info
        self._attr_unique_id = f"{installation_id}_{metric.unique_id}"
        self._attr_suggested_display_precision = metric.precision
        # Always set translation_key so HA can resolve
        # state/option translations (e.g. select options).
        self._attr_translation_key = metric.generic_short_id.replace("{", "").replace(
            "}", ""
        )
        self._attr_translation_placeholders = metric.key_values
        # When main_topic is set, override name to None so
        # HA uses the device name (via _attr_has_entity_name).
        if metric.main_topic:
            self._attr_name = None

        self._attr_entity_category = (
            EntityCategory.DIAGNOSTIC
            if metric.generic_short_id in ENTITIES_CATEGORY_DIAGNOSTIC
            else None
        )
        self._attr_entity_registry_enabled_default = (
            metric.generic_short_id not in ENTITIES_DISABLE_BY_DEFAULT
        )

    def _native_unit_of_measurement(self) -> str | None:
        unit_of_measurement = self._metric.unit_of_measurement
        # We need to provide a native unit in three cases:
        if (
            # 1. Special units which will never need a translation and therefore will not be included in the translation file.
            unit_of_measurement in SPECIAL_NATIVE_UNITS
            # 2. When there is known device class which support multiple units. In this case
            # we publish what we have and HA will allow conversion to other supported units.
            # We specifically don't put those cases in the translation file by the merge script
            # not to waste translation resources so it has to come from here.
            or self._attr_device_class is not None
            # 3. Dynamic units come from user-configured MQTT topics (e.g.
            # SwitchableOutput Settings/Unit) and have no translation file
            # entry, so we must set the unit programmatically.
            or self._metric.metric_type == MetricType.DYNAMIC
        ):
            return unit_of_measurement

        return None

    @callback
    @abstractmethod
    def _on_update_cb(self, value: Any) -> None:
        """Handle the metric update. Must be implemented by subclasses."""

    @callback
    def _on_update(self, _: VictronVenusMetric, value: Any) -> None:
        self._on_update_cb(value)

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._metric.on_update = self._on_update

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        # Unregister update callback
        self._metric.on_update = None
        await super().async_will_remove_from_hass()
