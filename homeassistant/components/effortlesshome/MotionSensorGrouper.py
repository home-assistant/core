"""Motion Sensor Grouper module for EffortlessHome."""

import logging

from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)


class MotionSensorGrouper:
    """Class to group motion sensors by area."""

    def __init__(self, hass) -> None:
        """Initialize the motion sensor grouper."""
        self.hass = hass
        _LOGGER.debug("[MotionSensorGrouper] Initialized with hass object.")

    async def create_sensor_groups(self) -> None:
        """Create groups of motion sensors by area."""
        _LOGGER.debug("[MotionSensorGrouper] create_sensor_groups called.")
        areas = ar.async_get(self.hass)
        entities = er.async_get(self.hass)
        for area_id, area in areas.areas.items():
            _LOGGER.debug(
                "[MotionSensorGrouper] Processing area: %s (ID: %s)", area.name, area_id
            )
            motion_sensors = [
                entity.entity_id
                for entity in entities.entities.values()
                if (
                    entity.original_device_class in ("motion", "occupancy", "presence")
                    or entity.entity_id.startswith("media_player.")
                )
                and entity.area_id == area_id
            ]
            _LOGGER.debug(
                "[MotionSensorGrouper] Found motion sensors for area '%s': %s",
                area.name,
                motion_sensors,
            )
            group_name = f"group.motion_sensors_{area.name.lower().replace(' ', '_')}"
            await self._create_group(group_name, motion_sensors)

    async def create_security_sensor_group(self) -> None:
        """Create a group of motion sensors for security alarm."""
        _LOGGER.debug("[MotionSensorGrouper] create_security_sensor_group called.")
        entities = er.async_get(self.hass)
        motion_sensors = []
        for entity in entities.entities.values():
            if (
                entity.original_device_class in ("motion", "occupancy", "presence")
                and entity.entity_id not in (
                    "binary_sensor.security_motion_sensors_group",
                    "binary_sensor.security_motion_group_sensor",
                    "group.security_motion_sensors_group",
                )
                and entity.labels is not None
                and not self.checkforlabel(entity.labels, "notforsecuritymonitoring")
            ):
                _LOGGER.debug(
                    "[MotionSensorGrouper] Adding entity to security group: %s (labels: %s)",
                    entity.entity_id,
                    entity.labels,
                )
                motion_sensors.append(entity.entity_id)
        _LOGGER.debug(
            "[MotionSensorGrouper] Security motion sensors: %s",
            motion_sensors,
        )
        await self._create_group("group.security_motion_sensors_group", motion_sensors)

    def checkforlabel(self, labels, value_to_check) -> bool:
        """Check whether a label is in the list of labels."""
        parsed_labels = [label for label in labels if label] if labels else []
        _LOGGER.debug(
            "[MotionSensorGrouper] Checking for label '%s' in labels: %s",
            value_to_check,
            parsed_labels,
        )
        if value_to_check in parsed_labels:
            _LOGGER.debug(
                "[MotionSensorGrouper] '%s' is in parsed_labels.",
                value_to_check,
            )
            return True
        _LOGGER.debug(
            "[MotionSensorGrouper] '%s' is not in parsed_labels.",
            value_to_check,
        )
        return False

    async def _create_group(self, group_name, entity_ids) -> None:  # noqa: ANN001
        """Create a group of entities in Home Assistant."""
        _LOGGER.debug(
            "[MotionSensorGrouper] Creating group '%s' with entities: %s",
            group_name,
            entity_ids,
        )
        service_data = {
            "object_id": group_name.split(".")[-1],
            "name": group_name.split(".")[-1].replace("_", " ").title(),
            "entities": entity_ids,
        }
        await self.hass.services.async_call("group", "set", service_data, blocking=True)
        _LOGGER.debug(
            "[MotionSensorGrouper] Group '%s' created with entities: %s",
            group_name,
            entity_ids,
        )
