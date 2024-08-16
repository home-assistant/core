"""Setup Supported AWS Sensors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SERVICE_EC2
from .coordinator import AwsDataEC2ServicesCoordinator
from .entity import AwsDataEC2RegionEntity


@dataclass(frozen=True, kw_only=True)
class AwsDataRegionDescription(SensorEntityDescription):
    """Describes AWS Sensor entity."""

    unique_id_tag: str


SENSOR_TYPES: tuple[AwsDataRegionDescription, ...] = (
    AwsDataRegionDescription(
        key="CPUUtilization",
        translation_key="CPUUtilization",
        unique_id_tag="CPUUtilization",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwsDataRegionDescription(
        key="NetworkOut",
        translation_key="NetworkOut",
        unique_id_tag="NetworkOut",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwsDataRegionDescription(
        key="EBSWriteBytes",
        translation_key="EBSWriteBytes",
        unique_id_tag="EBSWriteBytes",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwsDataRegionDescription(
        key="EBSReadBytes",
        translation_key="EBSReadBytes",
        unique_id_tag="EBSReadBytes",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AWS Sensors."""

    stored_coord: dict[str, dict] = entry.runtime_data
    sensors = []
    if SERVICE_EC2 in stored_coord:
        ec2_coord: AwsDataEC2ServicesCoordinator = stored_coord["coord"][SERVICE_EC2]
        ec2_first_data: dict[str, Any] = ec2_coord.data
        sensors.append(
            [
                AWSDataEC2Sensor(
                    ec2_coord,
                    desc,
                    ec2_first_data[SERVICE_EC2][ec2]["Region"],
                    SERVICE_EC2,
                    metric,
                )
                for ec2 in ec2_first_data[SERVICE_EC2]
                for metric in ec2_first_data[SERVICE_EC2][ec2]["Metric"]
                for desc in ec2_first_data[SERVICE_EC2][ec2]["Metric"][metric]
                if desc.key == metric
            ]
        )


class AWSDataEC2Sensor(AwsDataEC2RegionEntity, SensorEntity):
    """Define a AWS EC2 sensor."""

    entity_description: AwsDataRegionDescription

    def __init__(
        self,
        coordinator: AwsDataEC2ServicesCoordinator,
        description: AwsDataRegionDescription,
        item_region: str,
        item_service: str,
        item_metric: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._item_region = item_region
        self._item_service = item_service
        self._item_metric = item_region

    @property
    def unique_id(self) -> str:
        """Return the uuid as the unique_id."""
        return self._item_region

    @property
    def native_value(self) -> int:
        """Return the state."""
        return 0

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the entity."""
        return {}
