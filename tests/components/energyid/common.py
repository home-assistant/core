"""Common Mock Objects for all tests."""

from dataclasses import dataclass
import datetime as dt
from typing import Any

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
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, EventStateChangedData, State

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

    def __init__(
        self,
        *,
        data: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the config entry."""
        super().__init__(
            domain=DOMAIN,
            data=data or MOCK_CONFIG_ENTRY_DATA,
            options=options or {},
        )


class MockMeterCatalog(MeterCatalog):
    """Mock Meter Catalog."""

    def __init__(self, meters: list[dict[str, Any]] | None = None) -> None:
        """Initialize the Meter Catalog."""
        super().__init__(
            meters or [{"metrics": {"test-metric": {"units": ["test-unit"]}}}]
        )


class MockWebhookPolicy(WebhookPolicy):
    """Mock Webhook Policy."""

    def __init__(self, policy: dict[str, Any] | None = None) -> None:
        """Initialize the Webhook Policy."""
        super().__init__(policy or {"allowedInterval": "P1D"})

    @classmethod
    async def async_init(
        cls, policy: dict[str, Any] | None = None
    ) -> "MockWebhookPolicy":
        """Mock async_init."""
        return cls(policy=policy)


class MockHass:
    """Mock Home Assistant."""

    class MockStates:
        """Mock States."""

        def async_entity_ids(self) -> list[str]:
            """Mock async_entity_ids."""
            return ["test-entity-id"]

    states = MockStates()


@dataclass
class MockState(State):
    """Mock State that inherits from Home Assistant State."""

    state: str
    attributes: dict[str, Any]
    last_changed: dt.datetime

    def __init__(
        self,
        state: Any,
        last_changed: dt.datetime | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the state."""
        # Convert state to string as required by Home Assistant
        str_state = str(state)
        # Initialize with required attributes
        self.attributes = attributes or {"unit_of_measurement": "kWh"}
        self.last_changed = last_changed or dt.datetime.now()
        # Use a valid entity ID format
        super().__init__("sensor.test_entity_id", str_state, self.attributes)


class MockEvent(Event[EventStateChangedData]):
    """Mock Event that properly implements Event[EventStateChangedData]."""

    def __init__(self, *, data: dict[str, Any] | None = None) -> None:
        """Initialize the event."""
        if data is None:
            data = {"new_state": MockState(1.0)}

        # Ensure we have the correct event data structure
        event_data = EventStateChangedData(
            entity_id="test-entity-id",
            new_state=data.get("new_state"),
            old_state=data.get("old_state"),
        )

        super().__init__(
            event_type=EVENT_STATE_CHANGED,
            data=event_data,
        )
