"""Tests for MQTT entities in Victron Remote Monitoring."""

from __future__ import annotations

import pytest
from victron_mqtt import MetricKind, MetricNature, MetricType

from homeassistant.components.victron_remote_monitoring import (
    button as vrm_button,
    number as vrm_number,
    select as vrm_select,
    switch as vrm_switch,
    time as vrm_time,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FakeDevice, FakeMetric, FakeWritableMetric

from tests.common import MockConfigEntry
from tests.conftest import SnapshotAssertion


@pytest.fixture
def mqtt_metrics() -> list[tuple[FakeDevice, FakeMetric]]:
    """Return MQTT metrics used for entity discovery."""
    device = FakeDevice(
        unique_id="device_1",
        device_id="1",
        name="Cerbo GX",
        manufacturer="Victron Energy",
        model="Cerbo GX",
        serial_number="ABC123",
    )

    return [
        (
            device,
            FakeMetric(
                metric_kind=MetricKind.SENSOR,
                metric_type=MetricType.VOLTAGE,
                metric_nature=MetricNature.INSTANTANEOUS,
                unit_of_measurement="V",
                precision=1,
                short_id="system_voltage",
                unique_id="system_0_voltage",
                name="System voltage",
                value=12.3,
            ),
        ),
        (
            device,
            FakeMetric(
                metric_kind=MetricKind.BINARY_SENSOR,
                metric_type=MetricType.TIME,
                metric_nature=MetricNature.INSTANTANEOUS,
                unit_of_measurement=None,
                precision=None,
                short_id="system_relay_state",
                unique_id="system_0_relay",
                name="System relay",
                value="On",
            ),
        ),
        (
            device,
            FakeWritableMetric(
                metric_kind=MetricKind.NUMBER,
                metric_type=MetricType.CURRENT,
                metric_nature=MetricNature.INSTANTANEOUS,
                unit_of_measurement="A",
                precision=1,
                short_id="charge_limit",
                unique_id="charger_0_limit",
                name="Charge limit",
                value=10.5,
                min_value=0.0,
                max_value=50.0,
                step=0.5,
            ),
        ),
        (
            device,
            FakeWritableMetric(
                metric_kind=MetricKind.SELECT,
                metric_type=MetricType.TIME,
                metric_nature=MetricNature.INSTANTANEOUS,
                unit_of_measurement=None,
                precision=None,
                short_id="system_mode",
                unique_id="system_0_mode",
                name="System mode",
                value="On",
                enum_values=["On", "Off"],
            ),
        ),
        (
            device,
            FakeWritableMetric(
                metric_kind=MetricKind.SWITCH,
                metric_type=MetricType.TIME,
                metric_nature=MetricNature.INSTANTANEOUS,
                unit_of_measurement=None,
                precision=None,
                short_id="system_switch",
                unique_id="system_0_switch",
                name="System switch",
                value="On",
            ),
        ),
        (
            device,
            FakeWritableMetric(
                metric_kind=MetricKind.BUTTON,
                metric_type=MetricType.TIME,
                metric_nature=MetricNature.INSTANTANEOUS,
                unit_of_measurement=None,
                precision=None,
                short_id="system_reboot",
                unique_id="system_0_reboot",
                name="System reboot",
                value=None,
            ),
        ),
        (
            device,
            FakeWritableMetric(
                metric_kind=MetricKind.TIME,
                metric_type=MetricType.TIME,
                metric_nature=MetricNature.INSTANTANEOUS,
                unit_of_measurement="min",
                precision=None,
                short_id="quiet_hours_start",
                unique_id="system_0_quiet_hours_start",
                name="Quiet hours start",
                value=480,
            ),
        ),
    ]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_mqtt_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Snapshot MQTT entities created from MQTT metrics."""
    monkeypatch.setattr(vrm_number, "VictronWritableMetric", FakeWritableMetric)
    monkeypatch.setattr(vrm_select, "VictronWritableMetric", FakeWritableMetric)
    monkeypatch.setattr(vrm_switch, "VictronWritableMetric", FakeWritableMetric)
    monkeypatch.setattr(vrm_button, "VictronWritableMetric", FakeWritableMetric)
    monkeypatch.setattr(vrm_time, "VictronWritableMetric", FakeWritableMetric)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    mqtt_entries = [entry for entry in entries if "|" not in entry.unique_id]
    assert mqtt_entries

    mqtt_entries_snapshot = [
        {
            "entity_id": entry.entity_id,
            "unique_id": entry.unique_id,
            "platform": entry.platform,
            "domain": entry.domain,
            "original_name": entry.original_name,
        }
        for entry in sorted(mqtt_entries, key=lambda item: item.entity_id)
    ]

    states_snapshot = {
        state.entity_id: {
            "state": state.state,
            "attributes": {
                key: value
                for key, value in state.attributes.items()
                if key in {"friendly_name", "unit_of_measurement", "options"}
            },
        }
        for entry in mqtt_entries
        if (state := hass.states.get(entry.entity_id)) is not None
    }

    assert mqtt_entries_snapshot == snapshot
    assert states_snapshot == snapshot
