"""Common fixtures for the EnergyID tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import aiohttp
from energyid_webhooks import WebhookPayload
from energyid_webhooks.metercatalog import MeterCatalog
from energyid_webhooks.webhookpolicy import WebhookPolicy
import pytest

from homeassistant.components.energyid.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.energyid.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


class MockEnergyIDConfigEntry(MockConfigEntry):
    """Mock config entry for EnergyID."""

    def __init__(self, *, data: dict = None, options: dict = None) -> None:
        """Initialize the config entry."""
        super().__init__(
            domain=DOMAIN,
            data=data
            or {
                "webhook_url": "https://hooks.energyid.eu/services/WebhookIn/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/xxxxxxxxxxxx",
                "entity_id": "test-entity-id",
                "metric": "test-metric",
                "metric_kind": "cumulative",
                "unit": "test-unit",
            },
            options=options or {},
        )


class MockWebhookClientAsync:
    """Mock WebhookClientAsync."""

    def __init__(
        self,
        webhook_url: str,
        url_valid: bool = True,
        can_connect: bool = True,
        **kwargs,
    ) -> None:
        """Initialize."""
        self.webhook_url = webhook_url
        self.url_valid = url_valid
        self.can_connect = can_connect

    @property
    async def policy(self) -> WebhookPolicy:
        """Return policy."""
        return await self.get_policy()

    async def get_policy(self) -> WebhookPolicy:
        """Get policy."""
        if self.url_valid and self.can_connect:
            return WebhookPolicy(policy={"allowedInterval": "P1D"})
        elif not self.url_valid:
            raise aiohttp.InvalidURL(url=self.webhook_url)
        elif not self.can_connect:
            request_info = aiohttp.RequestInfo(
                url=self.webhook_url,
                method="GET",
                headers={},
                real_url=self.webhook_url,
            )
            raise aiohttp.ClientResponseError(request_info, None, status=400)

    async def get_meter_catalog(self) -> MeterCatalog:
        """Get meter catalog."""
        return MeterCatalog(meters=[])

    async def post_payload(self, payload: WebhookPayload) -> None:
        """Post payload."""
        if not self.url_valid:
            raise aiohttp.InvalidURL(url=self.webhook_url)
        elif not self.can_connect:
            request_info = aiohttp.RequestInfo(
                url=self.webhook_url,
                method="POST",
                headers={},
                real_url=self.webhook_url,
            )
            raise aiohttp.ClientResponseError(request_info, None, status=400)
