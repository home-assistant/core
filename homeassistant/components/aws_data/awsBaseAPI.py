"""Base API for AWS."""

import asyncio
from collections.abc import Callable

from botocore.client import BaseClient
from botocore.config import Config
from botocore.session import Session


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
        return Session().create_client(
            serviceName,
            aws_access_key_id=self._key_id,
            aws_secret_access_key=self._key_secret,
            config=self._defaultConfig.merge(conf),
        )

    async def serviceCall(self, client: BaseClient, func: str, callback: Callable):
        """Service call in async task."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._asyncServiceCall, client, func, callback
        )

    def _asyncServiceCall(self, client: BaseClient, func: str, callback: Callable):
        """Call callback for calling services functions."""
        return callback(client, func)
