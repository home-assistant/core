"""Test ViCare binary sensors."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare


@pytest.mark.parametrize(
    "entity_id",
    [
        "burner",
        "circulation_pump",
        "frost_protection",
    ],
)
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_vicare_gas_boiler: MagicMock,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the ViCare binary sensor."""
    assert hass.states.get(f"binary_sensor.model0_{entity_id}") == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json"),
        Fixture({"type:radiator"}, "vicare/ZigbeeTRV.json"),
        Fixture({"type:repeater"}, "vicare/ZigbeeRepeater.json"),
        # FHT main and channel are the same physical zigbee node, so they share
        # a gateway; this lets the channel link to the main via via_device.
        Fixture({"type:fhtMain"}, "vicare/FHTMain.json", gateway_id="fht_gateway"),
        Fixture(
            {"type:fhtChannel"}, "vicare/FHTChannel.json", gateway_id="fht_gateway"
        ),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}.PyViCare", return_value=MockPyViCare(fixtures)),
        patch(f"{MODULE}.PLATFORMS", [Platform.BINARY_SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_holiday(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the holiday program while it is scheduled."""
    vicare = MockPyViCare([Fixture({"type:heatpump"}, "vicare/Vitocal250A.json")])
    for feature in vicare.services["gateway0"]._features["deviceId0"]:
        if feature["feature"] == "heating.operating.programs.holiday":
            feature["properties"]["active"]["value"] = True
            feature["properties"]["start"]["value"] = "2026-11-02"
            feature["properties"]["end"]["value"] = "2026-11-15"
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}.PyViCare", return_value=vicare),
        patch(f"{MODULE}.PLATFORMS", [Platform.BINARY_SENSOR, Platform.SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    for entity_id in (
        "binary_sensor.model0_holiday",
        "binary_sensor.model0_holiday_at_home",
    ):
        await async_update_entity(hass, entity_id)

    assert hass.states.get("binary_sensor.model0_holiday").state == STATE_ON
    assert hass.states.get("sensor.model0_holiday_start").state == "2026-11-02"
    assert hass.states.get("sensor.model0_holiday_end").state == "2026-11-15"
    # the device reports 2000-01-01 for a holiday at home that is not scheduled
    assert hass.states.get("binary_sensor.model0_holiday_at_home").state == STATE_OFF
    assert hass.states.get("sensor.model0_holiday_at_home_start").state == STATE_UNKNOWN
