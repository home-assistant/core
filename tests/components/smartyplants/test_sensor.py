"""Tests for the SmartyPlants sensor platform."""

from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pysmartyplants import (
    SmartyPlantsAuthError,
    SmartyPlantsConnectionError,
    SmartyPlantsError,
    SmartyPlantsForbiddenError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smartyplants.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

TEMPERATURE = "sensor.monstera_temperature"


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test every entity created from the first poll."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registered for a sensor."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "sensor-1"), mock_config_entry.entry_id
    )
    assert device == snapshot


@pytest.mark.parametrize(
    ("path", "value", "entity_id", "expected"),
    [
        pytest.param(
            ("readings",), None, TEMPERATURE, STATE_UNKNOWN, id="never_reported"
        ),
        pytest.param(
            ("readings", "moisture", "value"),
            "-",
            "sensor.monstera_soil_moisture",
            STATE_UNKNOWN,
            id="placeholder",
        ),
        pytest.param(
            ("readings", "moisture", "value"),
            "41",
            "sensor.monstera_soil_moisture",
            "41.0",
            id="numeric_string",
        ),
        pytest.param(
            ("readings", "fertiliser", "isCalculating"),
            True,
            "sensor.monstera_fertilize_in",
            STATE_UNKNOWN,
            id="calculating",
        ),
        pytest.param(
            ("isOnline",), False, TEMPERATURE, STATE_UNAVAILABLE, id="offline"
        ),
    ],
)
@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_reading_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sensor_payloads: list[dict[str, Any]],
    path: tuple[str, ...],
    value: Any,
    entity_id: str,
    expected: str,
) -> None:
    """Test how an unusual reading is represented."""
    target = sensor_payloads[0]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == expected


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_temperature_follows_the_backend_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sensor_payloads: list[dict[str, Any]],
) -> None:
    """Test a reading sent in Fahrenheit is read as Fahrenheit."""
    temperature = sensor_payloads[0]["readings"]["temperature"]
    temperature["unit"] = "°F"
    temperature["value"] = 72.5

    await setup_integration(hass, mock_config_entry)

    # Read as Celsius it would stay 72.5; (72.5 - 32) * 5 / 9 = 22.5.
    state = hass.states.get(TEMPERATURE)
    assert state.state == "22.5"
    assert state.attributes["unit_of_measurement"] == "°C"


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_sensor_removed_from_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sensor_payloads: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor that leaves the account becomes unavailable."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(TEMPERATURE).state == "22.5"

    sensor_payloads.clear()
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("error", "translation_key", "placeholders"),
    [
        pytest.param(
            SmartyPlantsConnectionError("boom"),
            "cannot_connect",
            {"error": "boom"},
            id="connection",
        ),
        pytest.param(SmartyPlantsAuthError("nope"), "invalid_auth", None, id="auth"),
        pytest.param(
            SmartyPlantsForbiddenError(
                "This API key does not allow requests from 198.51.100.7."
            ),
            "forbidden",
            {"error": "This API key does not allow requests from 198.51.100.7."},
            id="forbidden",
        ),
    ],
)
async def test_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smartyplants_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    error: SmartyPlantsError,
    translation_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Test a failed poll marks entities unavailable and keeps the reason."""
    await setup_integration(hass, mock_config_entry)

    mock_smartyplants_client.async_get_sensors.side_effect = error
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE).state == STATE_UNAVAILABLE
    failure = mock_config_entry.runtime_data.last_exception
    assert isinstance(failure, UpdateFailed)
    assert failure.translation_key == translation_key
    assert failure.translation_placeholders == placeholders
