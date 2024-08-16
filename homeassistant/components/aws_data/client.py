"""Client Supporting aws calls."""

from __future__ import annotations

<<<<<<< HEAD
from botocore.client import BaseClient
=======
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
>>>>>>> 833ac3afab (Setup Coordinates)
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
<<<<<<< HEAD
        self, serviceName: str, operation: str, region: str | None = None
    ):
=======
        self,
        serviceName: str,
        operation: str,
        region: str | None = None,
        data: dict | list | None = None,
    ) -> dict[str, Any]:
>>>>>>> 833ac3afab (Setup Coordinates)
        """Service function call for supported services.

        Runs under separate async task to not block main loop.
        """

        client = await self._api.client(
            serviceName=serviceName, conf=Config(region_name=region)
        )

        return await self._api.serviceCall(
<<<<<<< HEAD
            client=client, func=operation, callback=self._callback
        )

    def _callback(self, client: BaseClient, func: str):
        """Client callback for supported operations."""
        data = {}
        try:
            if func == "id":
                data = client.get_caller_identity()

            if func == "list_regions":
                data = client.list_regions(
                    MaxResults=50,
                    RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"],
                )
            if func == "ec2_compute":
                _LOGGER.warning("Not Supported Yet")

            if func == "ec2_networkOut":
                _LOGGER.warning("Not Supported Yet")
                # data = self._ec2(region=region)

            client.close()
        except ClientError as e:
            _LOGGER.warning("Invalid Credentials: %s", e.response)
            return e.response

        return data
=======
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
                        yield from objects["Contents"]

                for cont in contents():
                    obj_count += 1
                    size += cont["Size"]

                result = {"Size": size, "Objects": obj_count}
            if func == "CloudWatch_Metrics":
                result = client.get_metric_data(
                    MetricDataQueries=data,
                    StartTime=datetime.now(UTC) - timedelta(seconds=900),
                    EndTime=datetime.now(UTC),
                )

            if func == "Cost":
                start_time = datetime.now(UTC)
                result = client.get_cost_and_usage(
                    TimePeriod={
                        "Start": start_time.strftime("%Y-%m-01"),
                        "End": datetime.now(UTC).strftime("%Y-%m-%d"),
                    },
                    Granularity="DAILY",
                    Metrics=["AmortizedCost"],
                )
            client.close()
        except ClientError as e:
            _LOGGER.warning("Invalid Credentials: %s", e.response)
            result = e.response
        _LOGGER.warning(result)
        return result

    @staticmethod
    def error(result: dict) -> dict:
        """Handle Errors."""
        errors: dict[str, str] = {}
        if "Error" in result:
            errors["base"] = "unknown"
            if result["Error"]["Code"] == "AccessDeniedException":
                errors["base"] = "access_denied"
                return errors
            if result["Error"]["Code"] == "InvalidClientTokenId":
                errors["base"] = "invalid_auth"
                return errors
            if result["Error"]["Code"] == "UnauthorizedOperation":
                errors["base"] = "unauthorized_operation"

        return errors
>>>>>>> 833ac3afab (Setup Coordinates)
