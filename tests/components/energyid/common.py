"""Common Mock Objects for all tests."""

import datetime as dt

from energyid_webhooks.metercatalog import MeterCatalog
from energyid_webhooks.webhookpolicy import WebhookPolicy

from homeassistant.components.energyid.const import (
    CONF_ENTITY_ID,
    CONF_METRIC,
    CONF_METRIC_KIND,
    CONF_UNIT,
    CONF_WEBHOOK_URL,
    DOMAIN,
)

from tests.common import MockConfigEntry

MOCK_CONFIG_ENTRY_DATA = {
    CONF_WEBHOOK_URL: "https://hooks.energyid.eu/services/WebhookIn/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/xxxxxxxxxxxx",
    CONF_ENTITY_ID: "test-entity-id",
    CONF_METRIC: "test-metric",
    CONF_METRIC_KIND: "cumulative",
    CONF_UNIT: "test-unit",
}


class MockEnergyIDConfigEntry(MockConfigEntry):
    """Mock config entry for EnergyID."""

    def __init__(self, *, data: dict = None, options: dict = None) -> None:
        """Initialize the config entry."""
        super().__init__(
            domain=DOMAIN,
            data=data or MOCK_CONFIG_ENTRY_DATA,
            options=options or {},
        )


class MockMeterCatalog(MeterCatalog):
    """Mock Meter Catalog."""

    def __init__(self, meters: list[dict] = None) -> None:
        """Initialize the Meter Catalog."""
        super().__init__(
            meters or [{"metrics": {"test-metric": {"units": ["test-unit"]}}}]
        )


class MockWebhookPolicy(WebhookPolicy):
    """Mock Webhook Policy."""

    def __init__(self, policy: dict = None) -> None:
        """Initialize the Webhook Policy."""
        super().__init__(policy or {"allowedInterval": "P1D"})

    @classmethod
    async def async_init(cls, policy: dict = None) -> "MockWebhookPolicy":
        """Mock async_init."""
        return cls(policy=policy)


class MockHass:
    """Mock Home Assistant."""

    class MockStates:
        """Mock States."""

        def async_entity_ids(self) -> list:
            """Mock async_entity_ids."""
            return ["test-entity-id"]

    states = MockStates()


class MockState:
    """Mock State."""

    def __init__(
        self, state, last_changed: dt.datetime = None, attributes: dict = None
    ) -> None:
        """Initialize the state."""
        self.state = state
        self.last_changed = last_changed or dt.datetime.now()
        self.attributes = attributes or {}


class MockEvent:
    """Mock Event."""

    def __init__(self, *, data: dict = None) -> None:
        """Initialize the event."""
        self.data = data or {"new_state": MockState(1.0)}
