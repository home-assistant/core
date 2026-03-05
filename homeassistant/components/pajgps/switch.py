"""
Platform for GPS alert switch integration.
Enables/disables alert types on PAJ GPS devices directly through the coordinator.
"""
from __future__ import annotations
import logging
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import ALERT_NAMES, ALERT_TYPE_TO_DEVICE_FIELD, ALERT_TYPE_TO_MODEL_FIELD
from .coordinator import PajGpsCoordinator
from .__init__ import PajGpsConfigEntry
_LOGGER = logging.getLogger(__name__)
class PajGPSAlertSwitch(CoordinatorEntity[PajGpsCoordinator], SwitchEntity):
    """
    Switch entity that enables or disables an alert type on a PAJ GPS device.
    Write path: fires an immediate PUT via the coordinator (no queue, no delay),
    then updates the snapshot optimistically.  Server confirmation arrives with
    the next device-tier refresh (~300 s).
    """
    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:bell-cog"
    def __init__(
        self, pajgps_coordinator: PajGpsCoordinator, device_id: int, alert_type: int
    ) -> None:
        super().__init__(pajgps_coordinator)
        self._device_id = device_id
        self._alert_type = alert_type
        alert_name = ALERT_NAMES.get(alert_type, "Unknown Alert")
        self._attr_unique_id = (
            f"pajgps_{pajgps_coordinator.entry_data['guid']}_{device_id}_switch_{alert_type}"
        )
        self._attr_name = alert_name
    @property
    def device_info(self) -> DeviceInfo | None:
        return self.coordinator.get_device_info(self._device_id)
    @property
    def is_on(self) -> bool | None:
        device = next(
            (d for d in self.coordinator.data.devices if d.id == self._device_id), None
        )
        if device is None:
            return None
        field = ALERT_TYPE_TO_DEVICE_FIELD.get(self._alert_type)
        if field is None:
            return None
        return bool(getattr(device, field, False))
    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_update_alert_state(self._device_id, self._alert_type, True)
    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_update_alert_state(self._device_id, self._alert_type, False)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PajGpsConfigEntry,
    async_add_entities,
) -> None:
    """Set up PAJ GPS alert switch entities from a config entry."""
    coordinator: PajGpsCoordinator = config_entry.runtime_data
    entities = []
    for device in coordinator.data.devices:
        if device.id is None:
            continue
        model = device.device_models[0] if device.device_models else {}
        for alert_type, field in ALERT_TYPE_TO_DEVICE_FIELD.items():
            # Check hardware support via device_models — skip if the model does not
            # advertise this alert capability (field absent or == 0).
            model_field = ALERT_TYPE_TO_MODEL_FIELD.get(alert_type)
            if not model_field or not model.get(model_field):
                continue
            # Check presence (is not None), not truthiness — a value of 0 means
            # the alert is supported but currently disabled; it still needs an entity.
            if getattr(device, field, None) is not None:
                entities.append(PajGPSAlertSwitch(coordinator, device.id, alert_type))
    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.warning("No PAJ GPS alert switch entities to add")
