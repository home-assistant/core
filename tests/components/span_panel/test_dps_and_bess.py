"""Tests for GFE override buttons and BESS connected binary sensor."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from span_panel_api import SpanBatterySnapshot
from span_panel_api.exceptions import SpanPanelServerError

from homeassistant.components.span_panel.binary_sensor import BESS_CONNECTED_SENSOR
from homeassistant.components.span_panel.button import (
    GFE_OVERRIDE_DESCRIPTION,
    SpanPanelGFEOverrideButton,
)
from homeassistant.components.span_panel.helpers import has_bess

from .factories import SpanPanelSnapshotFactory

# ---------------------------------------------------------------------------
# BESS Connected Binary Sensor
# ---------------------------------------------------------------------------


class TestBessConnectedBinarySensor:
    """Tests for the bess_connected binary sensor."""

    def test_bess_connected_true(self) -> None:
        """Connected=True -> is_on=True."""
        snapshot = SpanPanelSnapshotFactory.create(
            battery=SpanBatterySnapshot(soe_percentage=85.0, connected=True),
        )
        assert BESS_CONNECTED_SENSOR.value_fn(snapshot) is True

    def test_bess_connected_false(self) -> None:
        """Connected=False -> is_on=False."""
        snapshot = SpanPanelSnapshotFactory.create(
            battery=SpanBatterySnapshot(soe_percentage=85.0, connected=False),
        )
        assert BESS_CONNECTED_SENSOR.value_fn(snapshot) is False

    def test_bess_connected_none(self) -> None:
        """Connected=None -> is_on=None."""
        snapshot = SpanPanelSnapshotFactory.create(
            battery=SpanBatterySnapshot(soe_percentage=85.0, connected=None),
        )
        assert BESS_CONNECTED_SENSOR.value_fn(snapshot) is None

    def test_bess_sensor_not_created_without_bess(self) -> None:
        """No BESS (soe_percentage=None) -> has_bess returns False."""
        snapshot = SpanPanelSnapshotFactory.create(
            battery=SpanBatterySnapshot(),
        )
        assert not has_bess(snapshot)

    def test_bess_sensor_created_with_bess(self) -> None:
        """BESS present (soe_percentage set) -> has_bess returns True."""
        snapshot = SpanPanelSnapshotFactory.create(
            battery=SpanBatterySnapshot(soe_percentage=85.0, connected=True),
        )
        assert has_bess(snapshot)


# ---------------------------------------------------------------------------
# GFE Override Buttons
# ---------------------------------------------------------------------------


def _make_gfe_coordinator(
    dominant_power_source: str | None = "GRID",
    battery: SpanBatterySnapshot | None = None,
) -> MagicMock:
    """Build a mock coordinator for GFE button tests."""
    snapshot = SpanPanelSnapshotFactory.create(
        dominant_power_source=dominant_power_source,
        battery=battery if battery is not None else SpanBatterySnapshot(),
    )

    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.title = "SPAN Panel"
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {}
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


class TestGFEOverrideButtons:
    """Tests for the GFE override button entities."""

    def test_grid_button_unique_id(self) -> None:
        """Grid override button has expected unique ID."""
        coordinator = _make_gfe_coordinator()
        button = SpanPanelGFEOverrideButton(
            coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID"
        )
        assert button._attr_unique_id is not None
        assert "gfe_override" in str(button._attr_unique_id)

    @pytest.mark.asyncio
    async def test_grid_button_press_publishes_grid(self) -> None:
        """Pressing the grid button calls set_dominant_power_source with GRID."""
        coordinator = _make_gfe_coordinator()
        button = SpanPanelGFEOverrideButton(
            coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID"
        )
        button.hass = MagicMock()

        coordinator.client = AsyncMock()
        coordinator.client.set_dominant_power_source = AsyncMock()

        await button.async_press()

        coordinator.client.set_dominant_power_source.assert_called_once_with("GRID")
        coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_button_missing_control_method(self) -> None:
        """Client without set_dominant_power_source method logs warning."""
        coordinator = _make_gfe_coordinator()
        button = SpanPanelGFEOverrideButton(
            coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID"
        )
        button.hass = MagicMock()

        # Client without set_dominant_power_source
        coordinator.client = MagicMock(spec=[])

        await button.async_press()

        # Should not raise, just log
        coordinator.async_request_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_button_server_error(self) -> None:
        """SpanPanelServerError triggers a notification."""
        coordinator = _make_gfe_coordinator()

        with patch(
            "homeassistant.components.span_panel.button.async_create_span_notification",
            new_callable=AsyncMock,
        ) as mock_notification:
            button = SpanPanelGFEOverrideButton(
                coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID"
            )
            button.hass = MagicMock()

            coordinator.client = AsyncMock()
            coordinator.client.set_dominant_power_source = AsyncMock(
                side_effect=SpanPanelServerError("test error")
            )

            await button.async_press()

            mock_notification.assert_called_once()

    def test_available_when_bess_offline_and_not_grid(self) -> None:
        """Button is available when BESS is offline and GFE is not GRID."""
        coordinator = _make_gfe_coordinator(
            dominant_power_source="BATTERY",
            battery=SpanBatterySnapshot(soe_percentage=50.0, connected=False),
        )
        coordinator.panel_offline = False
        button = SpanPanelGFEOverrideButton(
            coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID"
        )
        assert button.available is True

    def test_unavailable_when_bess_online(self) -> None:
        """Button is unavailable when BESS is communicating."""
        coordinator = _make_gfe_coordinator(
            dominant_power_source="BATTERY",
            battery=SpanBatterySnapshot(soe_percentage=50.0, connected=True),
        )
        coordinator.panel_offline = False
        button = SpanPanelGFEOverrideButton(
            coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID"
        )
        assert button.available is False

    def test_unavailable_when_gfe_is_grid(self) -> None:
        """Button is unavailable when GFE is already GRID."""
        coordinator = _make_gfe_coordinator(
            dominant_power_source="GRID",
            battery=SpanBatterySnapshot(soe_percentage=50.0, connected=False),
        )
        coordinator.panel_offline = False
        button = SpanPanelGFEOverrideButton(
            coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID"
        )
        assert button.available is False

    def test_available_when_no_bess(self) -> None:
        """Button is available when no BESS is commissioned and GFE is not GRID."""
        coordinator = _make_gfe_coordinator(
            dominant_power_source="BATTERY",
            battery=SpanBatterySnapshot(),
        )
        coordinator.panel_offline = False
        button = SpanPanelGFEOverrideButton(
            coordinator, GFE_OVERRIDE_DESCRIPTION, "GRID"
        )
        assert button.available is True
