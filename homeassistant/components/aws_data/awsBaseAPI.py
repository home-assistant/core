"""Base API for AWS."""

import asyncio
from collections.abc import Callable
<<<<<<< HEAD

from botocore.client import BaseClient
from botocore.config import Config
from botocore.session import Session
=======
from typing import Any

import boto3
from botocore.config import Config
>>>>>>> 833ac3afab (Setup Coordinates)


class awsBaseAPI:
    """API class for service calls."""

    def __init__(
        self, key_id: str, key_secret: str, accountID: str | None = None
    ) -> None:
        """Set up data for AWS Client Connection."""

        self._key_id = key_id
        self._key_secret = key_secret
        self._accountID = accountID
        self._defaultConfig = Config(
            connect_timeout=20,
            # region_name=self._region,
            retries={"max_attempts": 3, "mode": "standard"},
        )

    def setAccountID(self, accountID: str):
        """Set up account id."""
        self._accountID = accountID

    def getAccountID(self):
        """Get account id."""
        return self._accountID

    async def client(self, serviceName: str, conf: Config | None = None):
        """Build Client for blocking task."""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._asyncClient, serviceName, conf)

    def _asyncClient(self, serviceName: str, conf: Config | None = None):
        """Generate AWS Client Class."""
<<<<<<< HEAD
        return Session().create_client(
=======
        return boto3.client(
>>>>>>> 833ac3afab (Setup Coordinates)
            serviceName,
            aws_access_key_id=self._key_id,
            aws_secret_access_key=self._key_secret,
            config=self._defaultConfig.merge(conf),
        )

<<<<<<< HEAD
    async def serviceCall(self, client: BaseClient, func: str, callback: Callable):
        """Service call in async task."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._asyncServiceCall, client, func, callback
        )

    def _asyncServiceCall(self, client: BaseClient, func: str, callback: Callable):
        """Call callback for calling services functions."""
        return callback(client, func)
=======
    async def serviceCall(
        self,
        client: boto3.client,
        func: str,
        callback: Callable,
        data: dict | list | None = None,
    ) -> dict[str, Any]:
        """Service call in async task."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._asyncServiceCall, client, func, callback, data
        )

    def _asyncServiceCall(
        self,
        client: boto3.client,
        func: str,
        callback: Callable,
        data: dict | list | None = None,
    ):
        """Call callback for calling services functions."""
        return callback(client, func, data)
>>>>>>> 833ac3afab (Setup Coordinates)
