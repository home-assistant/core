"""Tests for Span Panel button entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from span_panel_api.exceptions import SpanPanelServerError

from homeassistant.components.span_panel.button import (
    GFE_OVERRIDE_DESCRIPTION,
    SpanPanelGFEOverrideButton,
    async_setup_entry,
)
from homeassistant.components.span_panel.const import DOMAIN
from homeassistant.core import HomeAssistant

from .factories import SpanBatterySnapshotFactory, SpanPanelSnapshotFactory

from tests.common import MockConfigEntry


def _make_button_coordinator(snapshot) -> MagicMock:
    """Create a coordinator-like mock for button tests."""
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.panel_offline = False
    coordinator.config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={},
        title="SPAN Panel",
        unique_id=snapshot.serial_number,
    )
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_gfe_override_button_success_refreshes_coordinator() -> None:
    """Successful override publishes to the panel and refreshes state."""
    snapshot = SpanPanelSnapshotFactory.create(
        battery=SpanBatterySnapshotFactory.create(connected=False),
        dominant_power_source="BATTERY",
    )
    coordinator = _make_button_coordinator(snapshot)
    coordinator.client = MagicMock()
    coordinator.client.set_dominant_power_source = AsyncMock()
    button = SpanPanelGFEOverrideButton(coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID")

    await button.async_press()

    coordinator.client.set_dominant_power_source.assert_awaited_once_with("GRID")
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_gfe_override_button_logs_when_client_lacks_support(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Buttons should return early when the client cannot publish overrides."""
    snapshot = SpanPanelSnapshotFactory.create(
        battery=SpanBatterySnapshotFactory.create(connected=False),
        dominant_power_source="BATTERY",
    )
    coordinator = _make_button_coordinator(snapshot)
    coordinator.client = object()
    button = SpanPanelGFEOverrideButton(coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID")

    caplog.set_level("WARNING")

    await button.async_press()

    assert "Client does not support GFE override" in caplog.text
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_gfe_override_button_server_error_creates_notification() -> None:
    """Server errors should notify the user that override failed."""
    snapshot = SpanPanelSnapshotFactory.create(
        battery=SpanBatterySnapshotFactory.create(connected=False),
        dominant_power_source="BATTERY",
    )
    coordinator = _make_button_coordinator(snapshot)
    coordinator.client = MagicMock()
    coordinator.client.set_dominant_power_source = AsyncMock(
        side_effect=SpanPanelServerError("unsupported")
    )
    button = SpanPanelGFEOverrideButton(coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID")
    button.hass = MagicMock()

    with patch(
        "homeassistant.components.span_panel.button.async_create_span_notification",
        new=AsyncMock(),
    ) as mock_notification:
        await button.async_press()

    mock_notification.assert_awaited_once()
    coordinator.async_request_refresh.assert_not_awaited()


def test_gfe_override_button_available_only_when_override_is_relevant() -> None:
    """Availability should reflect panel state and whether firmware already has control."""
    snapshot = SpanPanelSnapshotFactory.create(
        battery=SpanBatterySnapshotFactory.create(connected=False),
        dominant_power_source="BATTERY",
    )
    coordinator = _make_button_coordinator(snapshot)
    button = SpanPanelGFEOverrideButton(coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID")

    assert button.available is True

    coordinator.panel_offline = True
    assert button.available is False

    coordinator.panel_offline = False
    coordinator.data = SpanPanelSnapshotFactory.create(
        battery=SpanBatterySnapshotFactory.create(connected=True),
        dominant_power_source="BATTERY",
    )
    assert button.available is False

    coordinator.data = SpanPanelSnapshotFactory.create(
        battery=SpanBatterySnapshotFactory.create(connected=False),
        dominant_power_source="GRID",
    )
    assert button.available is False


@pytest.mark.asyncio
async def test_button_async_setup_entry_only_adds_button_for_mqtt_with_bess(
    hass: HomeAssistant,
) -> None:
    """Button platform should only expose the override when it can work."""

    class FakeSpanMqttClient:
        """Minimal client type used for isinstance checks."""

    snapshot = SpanPanelSnapshotFactory.create(
        battery=SpanBatterySnapshotFactory.create(connected=False),
        dominant_power_source="BATTERY",
    )
    coordinator = _make_button_coordinator(snapshot)
    coordinator.client = FakeSpanMqttClient()
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, title="SPAN Panel")
    config_entry.runtime_data = MagicMock(coordinator=coordinator)
    async_add_entities = MagicMock()

    with patch(
        "homeassistant.components.span_panel.button.SpanMqttClient", FakeSpanMqttClient
    ):
        await async_setup_entry(hass, config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], SpanPanelGFEOverrideButton)

    coordinator_no_bess = _make_button_coordinator(
        SpanPanelSnapshotFactory.create(
            battery=SpanBatterySnapshotFactory.create(soe_percentage=None)
        )
    )
    coordinator_no_bess.client = FakeSpanMqttClient()
    config_entry.runtime_data = MagicMock(coordinator=coordinator_no_bess)
    async_add_entities = MagicMock()

    with patch(
        "homeassistant.components.span_panel.button.SpanMqttClient", FakeSpanMqttClient
    ):
        await async_setup_entry(hass, config_entry, async_add_entities)

    assert async_add_entities.call_args.args[0] == []
