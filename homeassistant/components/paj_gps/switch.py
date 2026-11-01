"""Switch platform for PAJ GPS alert toggles."""

from dataclasses import dataclass, replace
from typing import Any, override

from pajgps_api.models.device import Device
from pajgps_api.pajgps_api_error import PajGpsApiError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PajGpsConfigEntry, PajGpsCoordinator
from .entity import PajGpsEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PajGpsAlertSwitchEntityDescription(SwitchEntityDescription):
    """Describes a PAJ GPS alert switch."""

    model_field: str


ALERT_SWITCH_DESCRIPTIONS: tuple[PajGpsAlertSwitchEntityDescription, ...] = (
    PajGpsAlertSwitchEntityDescription(
        key="alarmbewegung",
        translation_key="shock_alert",
        entity_category=EntityCategory.CONFIG,
        model_field="alarm_erschuetterung",
    ),
    PajGpsAlertSwitchEntityDescription(
        key="alarmakkuwarnung",
        translation_key="battery_alert",
        entity_category=EntityCategory.CONFIG,
        model_field="alarm_batteriestand",
    ),
    PajGpsAlertSwitchEntityDescription(
        key="alarmsos",
        translation_key="sos_alert",
        entity_category=EntityCategory.CONFIG,
        model_field="alarm_sos",
    ),
    PajGpsAlertSwitchEntityDescription(
        key="alarmgeschwindigkeit",
        translation_key="speed_alert",
        entity_category=EntityCategory.CONFIG,
        model_field="alarm_geschwindigkeit",
    ),
    PajGpsAlertSwitchEntityDescription(
        key="alarmstromunterbrechung",
        translation_key="power_cut_off_alert",
        entity_category=EntityCategory.CONFIG,
        model_field="alarm_stromunterbrechung",
    ),
    PajGpsAlertSwitchEntityDescription(
        key="alarmzuendalarm",
        translation_key="ignition_alert",
        entity_category=EntityCategory.CONFIG,
        model_field="alarm_zuendalarm",
    ),
    PajGpsAlertSwitchEntityDescription(
        key="alarm_fall_enabled",
        translation_key="drop_alert",
        entity_category=EntityCategory.CONFIG,
        model_field="alarm_drop",
    ),
    PajGpsAlertSwitchEntityDescription(
        key="alarm_volt",
        translation_key="voltage_alert",
        entity_category=EntityCategory.CONFIG,
        model_field="alarm_volt",
    ),
)


def _is_supported(
    device: Device, description: PajGpsAlertSwitchEntityDescription
) -> bool:
    """Return True if the device model supports the alert and the device reports it."""
    if not device.device_models:
        return False
    model_flag = getattr(device.device_models[0], description.model_field)
    return model_flag == 1 and getattr(device, description.key) is not None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PajGpsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PAJ GPS alert switch entities from a config entry."""
    coordinator = config_entry.runtime_data

    known_device_ids: set[int] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add entities for any device IDs not yet tracked."""
        current_ids = set(coordinator.data.devices.keys())
        new_ids = current_ids - known_device_ids
        if new_ids:
            sorted_new_ids = sorted(new_ids)
            async_add_entities(
                PajGpsAlertSwitch(coordinator, device_id, description)
                for device_id in sorted_new_ids
                for description in ALERT_SWITCH_DESCRIPTIONS
                if _is_supported(coordinator.data.devices[device_id], description)
            )
            known_device_ids.update(sorted_new_ids)

    _async_add_new_devices()

    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class PajGpsAlertSwitch(PajGpsEntity, SwitchEntity):
    """Switch that enables or disables one alert on a PAJ GPS device."""

    entity_description: PajGpsAlertSwitchEntityDescription

    def __init__(
        self,
        coordinator: PajGpsCoordinator,
        device_id: int,
        description: PajGpsAlertSwitchEntityDescription,
    ) -> None:
        """Initialize the alert switch entity."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.user_id}_{device_id}_{description.key}"

    @property
    @override
    def is_on(self) -> bool:
        """Return True when the alert is enabled on the device."""
        return bool(getattr(self.device, self.entity_description.key))

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the alert on the device."""
        await self._async_set_alert(1)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the alert on the device."""
        await self._async_set_alert(0)

    async def _async_set_alert(self, value: int) -> None:
        """Send the new alert value and store the device state returned by the API."""
        key = self.entity_description.key
        try:
            updated = await self.coordinator.api.update_device(
                self._device_id, **{key: value}
            )
        except PajGpsApiError as exc:
            raise HomeAssistantError(
                f"Failed to update {key} for device {self._device_id}: {exc}"
            ) from exc

        devices = {**self.coordinator.data.devices, self._device_id: updated}
        self.coordinator.data = replace(self.coordinator.data, devices=devices)
        self.coordinator.async_update_listeners()
