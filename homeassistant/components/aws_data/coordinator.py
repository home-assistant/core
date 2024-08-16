"""Define AWS Data DataUpdateCoordinator."""

from datetime import timedelta
from logging import Logger
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import AWSDataClient
from .const import (
    _LOGGER,
    CONST_ACCOUNT_ID,
    DOMAIN,
    EC2_METRIC_STATISTIC,
    SERVICE_CE,
    SERVICE_EC2,
    SERVICE_S3,
    USER_INPUT_DATA,
    USER_INPUT_ID,
    USER_INPUT_SECRET,
)


class AwsDataRegionCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator for Region Specific Data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        name: str,
        entry: ConfigEntry,
        regions: dict[str, Any],
        services: dict[str, Any],
        update_interval: timedelta,
    ) -> None:
        """Initialize Coordinator."""
        self.title = entry.title
        self._regions = regions
        self._services = services
        self._user_data = entry.data
        self._awsAPI: AWSDataClient = AWSDataClient(
            self._user_data[USER_INPUT_DATA][USER_INPUT_ID],
            self._user_data[USER_INPUT_DATA][USER_INPUT_SECRET],
            self._user_data[USER_INPUT_DATA][CONST_ACCOUNT_ID],
        )
        super().__init__(
            hass=hass,
            logger=logger,
            name=name,
            update_interval=update_interval,
        )

    def _cloudWatchMetric(
        self, namespace: str, metric: str, unit: str, Dimensions: list
    ):
        """Build Metric Query Dict."""
        return {
            "Id": metric.lower(),
            "MetricStat": {
                "Metric": {
                    "Namespace": namespace,
                    "MetricName": metric,
                    "Dimensions": Dimensions,
                },
                "Period": 300,
                "Stat": "Average",
                "Unit": unit,
            },
        }


class AwsDataEC2ServicesCoordinator(AwsDataRegionCoordinator):
    """Coordinator for Region Specific Data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        regions: dict,
        services: dict,
        update_interval: timedelta,
    ) -> None:
        """Initialize Data Coordinator."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            entry=entry,
            regions=regions,
            services=services,
            update_interval=update_interval,
        )

    async def _ec2_data(self) -> dict[str, Any]:
        """Retrieve EC2 Metric Data."""

        instances: dict[str, Any] = {}
        volume_filter: dict[str, Any] = {}
        for reg in self._regions:
            ec2 = await self._awsAPI.serviceCall(
                SERVICE_EC2,
                "ec2_list",
                data={
                    "Name": "instance-state-name",
                    "Values": [
                        "pending",
                        "running",
                        "shutting-down",
                        "stopping",
                        "stopped",
                    ],
                },
                region=reg,
            )
            if "Reservations" in ec2:
                for result in ec2["Reservations"]:
                    for inst in result["Instances"]:
                        instances[inst["InstanceId"]] = {
                            "KeyName": inst["KeyName"],
                            "Region": reg,
                            "State": inst["State"],
                            "Placement": inst["Placement"],
                            "BlockDeviceMappings": inst["BlockDeviceMappings"],
                            "Volumes": {},
                            "Metrics": {},
                        }

            volumes = await self._awsAPI.serviceCall(
                SERVICE_EC2, "ec2_storage_list", data=volume_filter
            )
            if "Volumes" in volumes:
                for vol in volumes["Volumes"]:
                    for attach in vol["Attachments"]:
                        if attach["InstanceId"] in instances:
                            instances[attach["InstanceId"]]["Volumes"][
                                vol["VolumeId"]
                            ] = {
                                "VolumeType": vol["VolumeType"],
                                "Iops": vol["Iops"],
                                "State": vol["State"],
                                "Size": vol["Size"],
                            }
            for inst in instances.items():
                metrics = await self._awsAPI.serviceCall(
                    "cloudwatch",
                    "CloudWatch_Metrics",
                    data=[
                        self._cloudWatchMetric(
                            "AWS/EC2",
                            metric_st["metric"],
                            metric_st["unit"],
                            [{"Name": "InstanceId", "Value": inst}],
                        )
                        for metric_st in EC2_METRIC_STATISTIC
                    ],
                )

                if "MetricDataResults" in metrics:
                    instances[inst]["Metrics"] = {
                        metric["Label"]: {
                            "Timestamps": metric["Timestamps"],
                            "Values": metric["Values"],
                        }
                        for metric in metrics["MetricDataResults"]
                    }

        return instances

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from AWS client library."""

        return {SERVICE_EC2: await self._ec2_data()}


class AwsDataS3ServicesCoordinator(AwsDataRegionCoordinator):
    """Coordinator for Region Specific Data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        regions: dict,
        services: dict,
        update_interval: timedelta,
    ) -> None:
        """Initialize Data Coordinator."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            entry=entry,
            regions=regions,
            services=services,
            update_interval=update_interval,
        )

    async def _s3_data(self):
        """Retrieve S3 Metric Data."""
        s3 = {}
        for reg in self._regions:
            s3_list = await self._awsAPI.serviceCall(SERVICE_S3, "s3_list", region=reg)
            if "Buckets" in s3_list:
                for bucket in s3_list["Buckets"]:
                    s3[bucket["Name"]] = {
                        "Name": bucket["Name"],
                        "CreationDate": bucket["CreationDate"],
                        "Region": reg,
                        "Metrics": {},
                    }
            for bucket in s3.items():
                s3_size = await self._awsAPI.serviceCall(
                    SERVICE_S3,
                    "bucket_size",
                    region=reg,
                    data={"Bucket": s3[bucket]["Name"], "Region": s3[bucket]["Region"]},
                )
                s3[bucket]["Metrics"] = s3_size

        return s3

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from AWS client library."""

        return {SERVICE_S3: await self._s3_data()}


class AwsDataCEServicesCoordinator(AwsDataRegionCoordinator):
    """Coordinator for Region Specific Data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        regions: dict,
        services: dict,
        update_interval: timedelta,
    ) -> None:
        """Initialize Data Coordinator."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            entry=entry,
            regions=regions,
            services=services,
            update_interval=update_interval,
        )

    async def _ce_data(self):
        """Retrieve S3 Metric Data."""
        ce_cost = await self._awsAPI.serviceCall(
            SERVICE_CE, "Cost", data={"Start": self.update_interval}
        )
        total_cost = 0.0
        if "ResultsByTime" in ce_cost:
            for cost in ce_cost["ResultsByTime"]:
                total_cost += float(cost["Total"]["AmortizedCost"]["Amount"])
        return {SERVICE_CE: total_cost}

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from AWS client library."""

        return {SERVICE_CE: await self._ce_data()}
