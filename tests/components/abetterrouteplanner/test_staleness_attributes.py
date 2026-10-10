"""Tests for the ``last_reported_at`` / ``provider`` sensor attributes."""

from datetime import UTC, datetime
from typing import Any

from aioabrp import Telemetry
from freezegun import freeze_time
import pytest

from homeassistant.components.abetterrouteplanner.const import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import MOCK_VEHICLE_ID, SENSOR_TEST_SUB, build_metric_value

from tests.common import MockConfigEntry

VOLTAGE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_voltage"
PROVIDER = "RIVIAN_STREAM"

# Object-id stem matching the mock vehicle's name, so a preseeded registry row
# fixes the entity_id instead of leaving it to the auto-slug.
_OBJECT_ID_STEM = "rivian_r2_2027_standard_long_range"


def _fire_voltage(
    fake_stream: Any, voltage: float, *, provider: str | None = None
) -> None:
    """Drive a single-voltage live frame through the fake telemetry stream."""
    fake_stream.fire_frame(
        MOCK_VEHICLE_ID,
        Telemetry(voltage=build_metric_value(voltage, provider=provider)),
    )


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    entity_registry: er.EntityRegistry | None = None,
    preseed_registry_keys: list[str] | None = None,
) -> None:
    """Set up the integration, optionally preseeding registry rows."""
    hass.set_state(CoreState.not_running)
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    if preseed_registry_keys and entity_registry is not None:
        for key in preseed_registry_keys:
            entity_registry.async_get_or_create(
                domain="sensor",
                platform=DOMAIN,
                unique_id=f"{SENSOR_TEST_SUB}_{MOCK_VEHICLE_ID}_{key}",
                config_entry=entry,
                suggested_object_id=f"{_OBJECT_ID_STEM}_{key}",
            )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_last_reported_at_stamps_per_metric_not_per_merged_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fake_stream: Any,
) -> None:
    """Stamp refreshes only on frames whose batch carries the voltage metric."""

    await _setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
    )

    t1 = datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 5, 24, 10, 5, 0, tzinfo=UTC)
    t3 = datetime(2026, 5, 24, 10, 10, 0, tzinfo=UTC)

    with freeze_time(t1):
        fake_stream.fire_frame(
            MOCK_VEHICLE_ID, Telemetry(voltage=build_metric_value(400.0))
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t2):
        # This batch carries soc only, so the voltage slot stays untouched.
        fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(soc=build_metric_value(50.0)))
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t1

    with freeze_time(t3):
        fake_stream.fire_frame(
            MOCK_VEHICLE_ID, Telemetry(voltage=build_metric_value(410.0))
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == t3


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_wire_time_is_preferred_over_receipt_time(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fake_stream: Any,
) -> None:
    """A reading carrying its own wire time is not stamped with arrival time."""

    await _setup(
        hass,
        config_entry_with_vehicles,
        entity_registry=entity_registry,
        preseed_registry_keys=["voltage"],
    )

    wire = datetime(2026, 5, 20, 8, 0, 0, tzinfo=UTC)
    with freeze_time(datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)):
        fake_stream.fire_frame(
            MOCK_VEHICLE_ID, Telemetry(voltage=build_metric_value(400.0, time=wire))
        )
        await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("last_reported_at") == wire


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        pytest.param(PROVIDER, PROVIDER, id="provider_surfaces"),
        pytest.param(None, None, id="provider_absent"),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_provider_attribute_follows_the_live_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    fake_stream: Any,
    provider: str | None,
    expected: str | None,
) -> None:
    """``provider`` appears only when the frame carries one."""

    await _setup(hass, config_entry_with_vehicles)

    _fire_voltage(fake_stream, 400.0, provider=provider)
    await hass.async_block_till_done()

    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("provider") == expected
