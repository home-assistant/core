"""
Platform for GPS binary sensor (alert) integration.
Reads notification data from PajGpsCoordinator to expose triggered alerts.
"""
from __future__ import annotations
import logging
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import ALERT_NAMES, ALERT_TYPE_TO_DEVICE_FIELD, ALERT_TYPE_TO_MODEL_FIELD
from .coordinator import PajGpsCoordinator
from .__init__ import PajGpsConfigEntry
_LOGGER = logging.getLogger(__name__)
class PajGPSAlertSensor(CoordinatorEntity[PajGpsCoordinator], BinarySensorEntity):
    """Binary sensor that is ON when an unread notification of a given type exists."""
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    def __init__(
        self, pajgps_coordinator: PajGpsCoordinator, device_id: int, alert_type: int
    ) -> None:
        super().__init__(pajgps_coordinator)
        self._device_id = device_id
        self._alert_type = alert_type
        alert_name = ALERT_NAMES.get(alert_type, "Unknown Alert")
        self._attr_unique_id = (
            f"pajgps_{pajgps_coordinator.entry_data['guid']}_{device_id}_alert_{alert_type}"
        )
        self._attr_name = alert_name
    @property
    def device_info(self) -> DeviceInfo | None:
        return self.coordinator.get_device_info(self._device_id)
    @property
    def is_on(self) -> bool:
        notifications = self.coordinator.data.notifications.get(self._device_id, [])
        return any(n.meldungtyp == self._alert_type for n in notifications)
    @property
    def icon(self) -> str:
        return "mdi:bell-alert" if self.is_on else "mdi:bell"
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PajGpsConfigEntry,
    async_add_entities,
) -> None:
    """Set up PAJ GPS binary sensor (alert) entities from a config entry."""
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
                entities.append(PajGPSAlertSensor(coordinator, device.id, alert_type))
    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.warning("No PAJ GPS alert entities to add")
