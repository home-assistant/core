"""Tests for Span Panel diagnostics."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.span_panel import SpanPanelRuntimeData
from homeassistant.components.span_panel.const import (
    CONF_EBUS_BROKER_PASSWORD,
    CONF_EBUS_BROKER_USERNAME,
    CONF_HOP_PASSPHRASE,
    DOMAIN,
)
from homeassistant.components.span_panel.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from .factories import (
    SpanBatterySnapshotFactory,
    SpanCircuitSnapshotFactory,
    SpanEvseSnapshotFactory,
    SpanPanelSnapshotFactory,
)

from tests.common import MockConfigEntry


async def test_config_entry_diagnostics_includes_redacted_runtime_data(
    hass: HomeAssistant,
) -> None:
    """Return redacted diagnostics with optional runtime sections populated."""
    snapshot = SpanPanelSnapshotFactory.create(
        serial_number="sp3-diag-001",
        firmware_version="spanos2/r202603/05",
        panel_size=32,
        wifi_ssid="Span WiFi",
        eth0_link=True,
        wlan_link=False,
        circuits={
            "uuid_kitchen": SpanCircuitSnapshotFactory.create(
                circuit_id="uuid_kitchen",
                name="Kitchen",
                relay_state="CLOSED",
                priority="SOC_THRESHOLD",
                instant_power_w=245.5,
                produced_energy_wh=10.0,
                consumed_energy_wh=2500.0,
                device_type="circuit",
                tabs=[5, 6],
            )
        },
        evse={"evse-0": SpanEvseSnapshotFactory.create()},
        battery=SpanBatterySnapshotFactory.create(
            connected=True,
            soe_percentage=84.0,
            soe_kwh=11.2,
        ),
    )
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.panel_offline = False
    coordinator.last_update_success = True

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: "access-secret",
            CONF_EBUS_BROKER_PASSWORD: "mqtt-password",
            CONF_EBUS_BROKER_USERNAME: "mqtt-user",
            CONF_HOP_PASSPHRASE: "hop-secret",
        },
        title="SPAN Panel",
        unique_id="sp3-diag-001",
    )
    entry.runtime_data = SpanPanelRuntimeData(coordinator=coordinator)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["config_entry"]["data"][CONF_ACCESS_TOKEN] == REDACTED
    assert result["config_entry"]["data"][CONF_EBUS_BROKER_PASSWORD] == REDACTED
    assert result["config_entry"]["data"][CONF_EBUS_BROKER_USERNAME] == REDACTED
    assert result["config_entry"]["data"][CONF_HOP_PASSPHRASE] == REDACTED

    assert result["panel"] == {
        "serial_number": "sp3-diag-001",
        "firmware_version": "spanos2/r202603/05",
        "panel_size": 32,
        "wifi_ssid": "Span WiFi",
        "eth0_link": True,
        "wlan_link": False,
    }
    assert result["circuits"]["uuid_kitchen"] == {
        "name": "Kitchen",
        "relay_state": "CLOSED",
        "priority": "SOC_THRESHOLD",
        "is_user_controllable": True,
        "instant_power_w": 245.5,
        "produced_energy_wh": 10.0,
        "consumed_energy_wh": 2500.0,
        "device_type": "circuit",
        "tabs": [5, 6],
    }
    assert result["evse"]["evse-0"] == {
        "node_id": "evse-0",
        "feed_circuit_id": "evse_circuit_1",
        "status": "CHARGING",
        "lock_state": "LOCKED",
        "advertised_current_a": 32.0,
    }
    assert result["battery"] == {
        "connected": True,
        "soe_percentage": 84.0,
        "soe_kwh": 11.2,
    }
    assert result["coordinator"] == {
        "panel_offline": False,
        "last_update_success": True,
    }


async def test_config_entry_diagnostics_omits_optional_sections_when_unavailable(
    hass: HomeAssistant,
) -> None:
    """Return empty optional sections when the snapshot lacks them."""
    snapshot = SimpleNamespace(
        serial_number="sp3-diag-002",
        firmware_version="spanos2/r202603/06",
        panel_size=None,
        wifi_ssid=None,
        eth0_link=None,
        wlan_link=None,
        circuits={
            "uuid_minimal": SimpleNamespace(
                name=None,
                relay_state="OPEN",
                priority="NEVER",
                is_user_controllable=False,
                instant_power_w=0.0,
                produced_energy_wh=0.0,
                consumed_energy_wh=0.0,
            )
        },
        evse={},
        battery=None,
    )
    coordinator = MagicMock()
    coordinator.data = snapshot
    coordinator.panel_offline = True
    coordinator.last_update_success = False

    entry = MockConfigEntry(domain=DOMAIN, data={}, title="SPAN Panel")
    entry.runtime_data = SpanPanelRuntimeData(coordinator=coordinator)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["panel"] == {
        "serial_number": "sp3-diag-002",
        "firmware_version": "spanos2/r202603/06",
        "panel_size": None,
    }
    assert result["circuits"]["uuid_minimal"] == {
        "name": None,
        "relay_state": "OPEN",
        "priority": "NEVER",
        "is_user_controllable": False,
        "instant_power_w": 0.0,
        "produced_energy_wh": 0.0,
        "consumed_energy_wh": 0.0,
    }
    assert result["evse"] == {}
    assert result["battery"] == {}
    assert result["coordinator"] == {
        "panel_offline": True,
        "last_update_success": False,
    }
