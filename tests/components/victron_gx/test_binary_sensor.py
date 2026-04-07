"""Tests for Victron GX MQTT binary sensors."""

from __future__ import annotations

import pytest
from victron_mqtt import Hub as VictronVenusHub, VictronEnum
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.victron_gx.binary_sensor import VictronBinarySensor
from homeassistant.components.victron_gx.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry


class _TestEnum(VictronEnum):
    UNKNOWN = (99, "unknown_id", "Unknown")


async def test_victron_binary_sensor(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test BINARY_SENSOR MetricKind - EV charger connected sensor is created and updated."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/evcharger/0/Connected",
        '{"value": 1}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entities) == 1
    entity = entities[0]
    assert entity.entity_id == "binary_sensor.ev_charging_station_connected"
    assert entity.unique_id == f"{MOCK_INSTALLATION_ID}_evcharger_0_evcharger_connected"
    assert entity.translation_key == "evcharger_connected"

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "on"

    # Verify device info was registered correctly
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_INSTALLATION_ID}_evcharger_0")}
    )
    assert device is not None
    assert device.manufacturer == "Victron Energy"

    # Update the metric to exercise the entity update callback path.
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/evcharger/0/Connected",
        '{"value": 0}',
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "off"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("not_an_enum", None),
        (_TestEnum.UNKNOWN, None),
    ],
)
def test_is_on_edge_cases(value: object, expected: bool | None) -> None:
    """Test _is_on returns None for non-VictronEnum and unknown enum IDs."""
    assert VictronBinarySensor._is_on(value) is expected
