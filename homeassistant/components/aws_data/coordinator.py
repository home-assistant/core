"""Define AWS Data DataUpdateCoordinator."""

from abc import abstractmethod
from datetime import timedelta
from logging import Logger
from statistics import fmean
from typing import Any, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import AWSDataClient
from .const import (
    _LOGGER,
    CONST_ACCOUNT,
    CONST_ACCOUNT_ID,
    CONST_AWS_REGION,
    CONST_FILTER,
    CONST_SERVICE_NAME,
    CONST_SERVICE_REASON,
    DOMAIN,
    DOMAIN_DATA,
    EC2_METRIC_STATISTIC,
    S3_METRIC_STATISTIC,
    SERVICE_CE,
    SERVICE_EC2,
    SERVICE_S3,
    U_ID,
    U_SECRET,
    USER_INPUT,
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
            self._user_data[USER_INPUT][U_ID],
            self._user_data[USER_INPUT][U_SECRET],
            self._user_data[USER_INPUT][CONST_ACCOUNT_ID],
        )
        super().__init__(
            hass=hass,
            logger=logger,
            name=name,
            update_interval=update_interval,
        )
        self._metrics: dict[str, Any] = {}

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

    def filter_data(self, service: str, reason: str = "Exclude") -> list:
        """Filter from Configuration File."""
        hass_data = self.hass.data.get(DOMAIN_DATA, {})
        current_account = self._user_data[USER_INPUT][CONST_ACCOUNT_ID]
        filters = []

        for filt in hass_data.get(CONST_FILTER, []):
            if (
                current_account == filt.get(CONST_ACCOUNT)
                and filt.get(CONST_SERVICE_NAME, "") == service
                and filt.get(CONST_SERVICE_REASON, "Exclude") == reason
            ):
                filters.extend(filt["id"])
        return filters

    @abstractmethod
    def get_metric(self, service_id: str, metric: str) -> float | str:
        """Abstract Method to get Coordinator data."""


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

    @override
    def get_metric(self, service_id: str, metric: str) -> float | str:
        """EC2 Metric Retrieval."""
        service = self._metrics[SERVICE_EC2].get(service_id, {"Metrics": {}})
        metrics = service.get("Metrics", {})
        stats = metrics.get(metric, {})
        avg = fmean(stats.get("Values", [0.0]))
        for item in EC2_METRIC_STATISTIC:
            if metric == item["metric"] and item["unit"] == "Bytes":
                avg *= 8

        return avg

    async def _ec2_data(self) -> dict[str, Any]:
        """Retrieve EC2 Metric Data."""

        instances: dict[str, Any] = {}
        filter_data_exc = self.filter_data(SERVICE_EC2)
        filter_data_inc = self.filter_data(SERVICE_EC2, reason="Include")
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
            for result in ec2.get("Reservations", []):
                for inst in result.get("Instances", []):

                    def filt(inst=inst) -> bool:
                        if inst["InstanceId"] not in filter_data_exc and (
                            not filter_data_inc or inst["InstanceId"] in filter_data_inc
                        ):
                            return True
                        return False

                    if filt():
                        instances[inst["InstanceId"]] = {
                            "KeyName": inst["KeyName"],
                            CONST_AWS_REGION: reg,
                            "State": inst["State"],
                            "Placement": inst["Placement"],
                            "Metrics": {},
                        }

            for inst, data in instances.items():
                metrics = await self._awsAPI.serviceCall(
                    "cloudwatch",
                    "CloudWatch_Metrics",
                    region=data[CONST_AWS_REGION],
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
                    data["Metrics"] = {
                        metric["Label"]: {
                            "Timestamps": metric["Timestamps"],
                            "Values": metric["Values"],
                        }
                        for metric in metrics["MetricDataResults"]
                    }

        return instances

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from AWS client library."""
        self._metrics = {SERVICE_EC2: await self._ec2_data()}
        return self._metrics


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

    @override
    def get_metric(self, service_id: str, metric: str) -> float | str:
        """S3 Metric Retrieval."""
        service = self._metrics[SERVICE_S3].get(service_id, {"Metrics": {}})

        value = float(service["Metrics"].get(metric, 0.0))
        for item in S3_METRIC_STATISTIC:
            if metric == item["metric"] and item["unit"] == "Bytes":
                value *= 8
        return value

    async def _s3_data(self):
        """Retrieve S3 Metric Data."""
        s3 = {}
        filter_data_exc = self.filter_data(SERVICE_S3)
        filter_data_inc = self.filter_data(SERVICE_S3, reason="Include")
        for reg in self._regions:
            s3_list = await self._awsAPI.serviceCall(SERVICE_S3, "s3_list", region=reg)
            for bucket in s3_list.get("Buckets", []):

                def filt(bucket=bucket) -> bool:
                    if bucket["Name"] not in filter_data_exc and (
                        not filter_data_inc or bucket["Name"] in filter_data_inc
                    ):
                        return True
                    return False

                if filt():
                    s3[bucket["Name"]] = {
                        "Name": bucket["Name"],
                        "CreationDate": bucket["CreationDate"],
                        CONST_AWS_REGION: reg,
                        "Metrics": {},
                    }

            for bucket, data in s3.items():
                s3_size = await self._awsAPI.serviceCall(
                    SERVICE_S3,
                    "bucket_size",
                    region=reg,
                    data={
                        "Bucket": bucket,
                        "Region": data[CONST_AWS_REGION],
                    },
                )
                data["Metrics"] = s3_size
        return s3

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from AWS client library."""
        self._metrics = {SERVICE_S3: await self._s3_data()}
        return self._metrics


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

    @override
    def get_metric(self, service_id: str, metric: str) -> float | str:
        """Cost Explorer Metric Retrieval."""
        service = self._metrics[SERVICE_CE].get(service_id, {"Metrics": {}})
        return float(service["Metrics"].get(metric, 0.0))

    async def _ce_data(self):
        """Retrieve Cost Explorer Metric Data."""
        ce_cost = await self._awsAPI.serviceCall(
            SERVICE_CE, "Cost", data={"Start": self.update_interval}
        )
        total_cost = 0.0
        for cost in ce_cost.get("ResultsByTime", []):
            total_cost += float(cost["Total"]["AmortizedCost"]["Amount"])

        return {"monthly_cost": total_cost}

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from AWS client library."""
        self._metrics = {SERVICE_CE: {"Global": {"Metrics": await self._ce_data()}}}
        return self._metrics
