"""Setup Supported AWS Sensors."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONST_AWS_REGION, DOMAIN, SERVICE_CE, SERVICE_EC2, SERVICE_S3
from .coordinator import (
    AwsDataCEServicesCoordinator,
    AwsDataEC2ServicesCoordinator,
    AwsDataRegionCoordinator,
    AwsDataS3ServicesCoordinator,
)
from .entity import AwsDataEntity


@dataclass(frozen=True, kw_only=True)
class AwsDataRegionDescription(SensorEntityDescription):
    """Describes AWS Sensor entity."""


SENSOR_TYPES: tuple[AwsDataRegionDescription, ...] = (
    AwsDataRegionDescription(
        key="CPUUtilization",
        translation_key="CPUUtilization",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwsDataRegionDescription(
        key="NetworkOut",
        translation_key="NetworkOut",
        native_unit_of_measurement="bit",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwsDataRegionDescription(
        key="EBSWriteBytes",
        translation_key="EBSWriteBytes",
        native_unit_of_measurement="bit",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwsDataRegionDescription(
        key="EBSReadBytes",
        translation_key="EBSReadBytes",
        native_unit_of_measurement="bit",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwsDataRegionDescription(
        key="s3_objects",
        translation_key="s3_objects",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwsDataRegionDescription(
        key="s3_size",
        translation_key="s3_size",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwsDataRegionDescription(
        key="monthly_cost",
        translation_key="monthly_cost",
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
    sensors: list[SensorEntity] = []
    if SERVICE_EC2 in stored_coord["coord"]:
        ec2_coord: AwsDataEC2ServicesCoordinator = stored_coord["coord"][SERVICE_EC2]
        ec2_first_data: dict[str, Any] = ec2_coord.data
        sensors.extend(
            [
                AWSDataSensor(
                    ec2_coord,
                    desc,
                    ec2,
                    SERVICE_EC2,
                    metric,
                    ec2_first_data[SERVICE_EC2][ec2][CONST_AWS_REGION],
                )
                for ec2 in ec2_first_data[SERVICE_EC2]
                for metric in ec2_first_data[SERVICE_EC2][ec2]["Metrics"]
                for desc in SENSOR_TYPES
                if desc.key == metric
            ]
        )

    if SERVICE_S3 in stored_coord["coord"]:
        s3_coord: AwsDataS3ServicesCoordinator = stored_coord["coord"][SERVICE_S3]
        s3_first_data: dict[str, Any] = s3_coord.data
        sensors.extend(
            [
                AWSDataSensor(
                    s3_coord,
                    desc,
                    s3,
                    SERVICE_S3,
                    metric,
                    s3_first_data[SERVICE_S3][s3][CONST_AWS_REGION],
                )
                for s3 in s3_first_data[SERVICE_S3]
                for metric in s3_first_data[SERVICE_S3][s3]["Metrics"]
                for desc in SENSOR_TYPES
                if desc.key == metric
            ]
        )

    if SERVICE_CE in stored_coord["coord"]:
        ce_coord: AwsDataCEServicesCoordinator = stored_coord["coord"][SERVICE_CE]
        ce_first_data: dict[str, Any] = ce_coord.data
        sensors.extend(
            [
                AWSDataSensor(ce_coord, desc, ce, SERVICE_CE, metric, "Global")
                for ce in ce_first_data[SERVICE_CE]
                for metric in ce_first_data[SERVICE_CE][ce]["Metrics"]
                for desc in SENSOR_TYPES
                if desc.key == metric
            ]
        )
    async_add_entities(sensors)


class AWSDataSensor(AwsDataEntity, SensorEntity):
    """Define a AWS EC2 sensor."""

    entity_description: AwsDataRegionDescription

    def __init__(
        self,
        coordinator: AwsDataRegionCoordinator,
        description: AwsDataRegionDescription,
        service_id: str,
        item_service: str,
        item_metric: str,
        item_region: str = "",
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._service_id = service_id
        self._item_region = item_region
        self._item_service = item_service
        self._item_metric = item_metric
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{self._item_region}_{self._item_service}_{self._service_id}")
            },
            name=f"{self._item_region}_{self._item_service}_{self._service_id}",
        )
        entity_id = f"{self._item_region}_{self._item_service}_{self._service_id}_{self._item_metric}"
        self._attr_unique_id = f"{sha256(entity_id.encode("utf-8")).hexdigest()}"
        self._attr_name = f"{self._item_metric}"

    @property
    def native_value(self) -> float | str:
        """Return the state."""
        return self.coordinator.get_metric(self._service_id, self._item_metric)

    @property
    def available(self) -> bool:
        """Return available Sensor Status."""
        return self.coordinator.last_update_success
