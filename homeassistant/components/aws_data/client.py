"""Client Supporting aws calls."""

from __future__ import annotations

from botocore.client import BaseClient
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
        self, serviceName: str, operation: str, region: str | None = None
    ):
        """Service function call for supported services.

        Runs under separate async task to not block main loop.
        """

        client = await self._api.client(
            serviceName=serviceName, conf=Config(region_name=region)
        )

        return await self._api.serviceCall(
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
