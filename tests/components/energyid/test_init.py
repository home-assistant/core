"""Tests for the EnergyID integration."""

import datetime as dt
from unittest.mock import patch

from homeassistant.components.energyid.__init__ import (
    WebhookDispatcher,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.core import HomeAssistant

from tests.components.energyid.conftest import (
    MockEnergyIDConfigEntry,
    MockWebhookClientAsync,
)


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry."""
    with patch(
        "homeassistant.components.energyid.__init__.WebhookClientAsync",
        MockWebhookClientAsync,
    ):
        entry = MockEnergyIDConfigEntry()
        assert await async_setup_entry(hass=hass, entry=entry) is True

        with patch(
            "homeassistant.components.energyid.__init__.WebhookDispatcher.async_validate_client",
            return_value=False,
        ):
            assert (
                await async_setup_entry(hass=hass, entry=MockEnergyIDConfigEntry())
                is False
            )

    assert await async_unload_entry(hass=hass, entry=entry) is True


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


async def test_dispatcher(hass: HomeAssistant) -> None:
    """Test dispatcher."""
    with patch(
        "homeassistant.components.energyid.__init__.WebhookClientAsync",
        MockWebhookClientAsync,
    ):
        dispatcher = WebhookDispatcher(hass, MockEnergyIDConfigEntry())

        # Test handle state change when the state is not castable as float
        event = MockEvent(data={"new_state": MockState("not a float")})
        assert await dispatcher.async_handle_state_change(event=event) is False

        # Test handle state change when the URL is not reachable
        dispatcher.client.can_connect = False
        event = MockEvent()
        assert await dispatcher.async_handle_state_change(event=event) is False
        # Validation should also fail in this case
        assert await dispatcher.async_validate_client() is False
        dispatcher.client.can_connect = True

        # Test handle state change of valid event
        event = MockEvent()
        assert await dispatcher.async_handle_state_change(event=event) is True

        # Test handle state change of an event that is too soon
        # Since the last event was less than 5 minutes ago, this should return None already
        event = MockEvent()
        assert await dispatcher.async_handle_state_change(event=event) is False


async def test_dispatcher_update_listener(hass: HomeAssistant) -> None:
    """Test dispatcher update listener."""
    dispatcher = WebhookDispatcher(hass, MockEnergyIDConfigEntry(options={}))

    update_entry = MockEnergyIDConfigEntry(
        options={"data_interval": "PT15M", "upload_interval": 420}
    )
    await dispatcher.update_listener(hass, update_entry)

    assert dispatcher.data_interval == "PT15M"
    assert dispatcher.upload_interval == dt.timedelta(seconds=420)
