"""Tests for the Overkiz sensor platform."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName, OverkizState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import async_deliver_events, build_event

from tests.common import snapshot_platform

TEMPERATURE_SENSOR = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#2",
    "sensor.garden_radiator_bathroom_temperature_sensor_temperature",
)
HEATING_BATTERY = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#1",
    "sensor.garden_radiator_battery_level",
)
TEMPERATURE_SENSOR_LOCAL = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe_3.json",
    "io://1234-5678--9373/1292684#2",
    "sensor.garden_temperature_sensor_temperature",
)
HOMEKIT_STACK = FixtureDevice(
    "setup/cloud_somfy_tahoma_switch_europe.json",
    "homekit://1234-5678-6867/stack",
    "sensor.tahoma_switch_homekit_setup_code",
)
# Device with core:MeasuredValueType attribute (test for dynamic unit resolution)
COZYTOUCH_DHW = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "io://1234-5678-5643/109286#2",
    "sensor.patio_water_heating_office_energy_meter_electric_energy_consumption",
)

SNAPSHOT_FIXTURES = [
    TEMPERATURE_SENSOR,
    TEMPERATURE_SENSOR_LOCAL,
    HOMEKIT_STACK,
    COZYTOUCH_DHW,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to sensor only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_sensor_temperature_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event-driven state update for a float sensor (temperature 24.4 → 22.1)."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert state
    assert state.state == "24.4"

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=TEMPERATURE_SENSOR.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_TEMPERATURE.value,
                        "type": 2,
                        "value": 22.1,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert state.state == "22.1"


async def test_sensor_battery_level_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event-driven state update for an integer sensor (battery 59 → 42)."""
    await setup_overkiz_integration(fixture=HEATING_BATTERY.fixture)

    state = hass.states.get(HEATING_BATTERY.entity_id)
    assert state
    assert state.state == "59"

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=HEATING_BATTERY.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_BATTERY_LEVEL.value,
                        "type": 2,
                        "value": 42.0,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(HEATING_BATTERY.entity_id)
    assert state.state == "42"


async def test_sensor_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_UNAVAILABLE.value,
                device_url=TEMPERATURE_SENSOR.device_url,
            )
        ],
    )

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE
