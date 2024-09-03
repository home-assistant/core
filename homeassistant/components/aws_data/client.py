"""Client Supporting aws calls."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .awsBaseAPI import awsBaseAPI
from .const import _LOGGER


class AWSDataClient:
    """AWS Wrapper for supported monitoring services."""

    def __init__(
        self, aws_key: str, aws_secret: str, accountID: str | None = None
    ) -> None:
        """Set up AWS Data Client."""

        self._api = awsBaseAPI(aws_key, aws_secret, accountID)

    def setAccountID(self, accountID):
        """Set up AWS account ID."""
        if self._api:
            self._api.setAccountID(accountID=accountID)

    def getAccountID(self):
        """Get up AWS account ID."""
        return self._api.getAccountID()

    async def serviceCall(
        self,
        serviceName: str,
        operation: str,
        region: str | None = None,
        data: dict | list | None = None,
    ) -> dict[str, Any]:
        """Service function call for supported services.

        Runs under separate async task to not block main loop.
        """

        client = await self._api.client(
            serviceName=serviceName, conf=Config(region_name=region)
        )

        return await self._api.serviceCall(
            client=client, func=operation, callback=self._callback, data=data
        )

    def _callback(
        self, client: boto3.client, func: str, data: dict | list | None = None
    ) -> dict[str, Any]:
        """Client callback for supported operations."""
        result: dict[str, Any] = {}
        try:
            if func == "id":
                result = client.get_caller_identity()

            if func == "list_regions":
                result = client.list_regions(
                    MaxResults=50,
                    RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"],
                )
            if func == "ec2_list":
                result = client.describe_instances(MaxResults=500, Filters=[data])
            if func == "ec2_storage_list":
                result = client.describe_volumes(MaxResults=500, Filters=[data])
            if func == "s3_list":
                result = client.list_buckets(MaxBuckets=500)
            if func == "bucket_size":
                size = 0
                obj_count = 0

                def contents():
                    continuation_token = None
                    isTruncated = True
                    while isTruncated:
                        list_kwargs = {"MaxKeys": 1000, "Bucket": data["Bucket"]}
                        if continuation_token:
                            list_kwargs["ContinuationToken"] = continuation_token
                        objects = client.list_objects_v2(**list_kwargs)
                        isTruncated = objects["IsTruncated"]
                        if "NextContinuationToken" in objects:
                            continuation_token = objects["NextContinuationToken"]
                        yield from objects.get("Contents", [])

                for cont in contents():
                    obj_count += 1
                    size += cont["Size"]

                result = {"s3_size": size, "s3_objects": obj_count}
            if func == "CloudWatch_Metrics":
                result = client.get_metric_data(
                    MetricDataQueries=data,
                    StartTime=datetime.now(UTC) - timedelta(seconds=900),
                    EndTime=datetime.now(UTC),
                )

            if func == "Cost":
                current_time = datetime.now(UTC)
                start_time: datetime = datetime.strptime(
                    f"{current_time.year}-{current_time.month}-1", "%Y-%m-%d"
                )
                if current_time.day == 1:
                    start_time = start_time - timedelta(days=1)
                result = client.get_cost_and_usage(
                    TimePeriod={
                        "Start": start_time.strftime("%Y-%m-%d"),
                        "End": current_time.strftime("%Y-%m-%d"),
                    },
                    Granularity="MONTHLY",
                    Metrics=["AmortizedCost"],
                )
            client.close()
        except ClientError as e:
            _LOGGER.warning("API Error Call: %s", e.response)
            result = e.response
        return result

    @staticmethod
    def error(result: dict) -> dict:
        """Handle Errors."""
        errors: dict[str, str] = {}
        error = result.get("Error", {})
        if error:
            errors["base"] = error.get("Code", "unknown")
            errors["message"] = error.get("Message", "Generic")
        return errors
