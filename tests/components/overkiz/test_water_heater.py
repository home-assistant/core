"""Tests for the Overkiz water_heater platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import OverkizState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.water_heater import ATTR_OPERATION_MODE, STATE_PERFORMANCE
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import (
    assert_command_call,
    assert_commands_call,
    async_deliver_events,
    device_state_changed_event,
)

from tests.common import snapshot_platform

# Thermor Malicio 2 (io:AtlanticDomesticHotWaterProductionV2_CE_FLAT_C2_IOComponent)
DHW_CE_FLAT_C2 = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "io://1234-5678-5643/109286#1",
    "water_heater.my_home_patio_water_heating",
)

# Hitachi Yutaki DHW (modbus:YutakiV2DHWTComponent)
DHW_HITACHI_YUTAKI = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "modbus://1234-5678-5643/6381497/1#4",
    "water_heater.yutaki_dhw",
)

SNAPSHOT_FIXTURES = [
    DHW_CE_FLAT_C2,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to water_heater only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.WATER_HEATER]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_water_heater_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_target_temperature_uses_water_target_state(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test target_temperature reads core:WaterTargetTemperatureState."""
    await setup_overkiz_integration(fixture=DHW_CE_FLAT_C2.fixture)

    state = hass.states.get(DHW_CE_FLAT_C2.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 60.0


# --- CE_FLAT_C2 (io:AtlanticDomesticHotWaterProductionV2_CE_FLAT_C2_IOComponent) ---
async def test_turn_away_mode_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test turning away mode on sends absence dates then setAbsenceMode prog."""
    freezer.move_to("2026-05-28 12:00:00+00:00")
    await setup_overkiz_integration(fixture=DHW_CE_FLAT_C2.fixture)

    await hass.services.async_call(
        "water_heater",
        "set_away_mode",
        {"entity_id": DHW_CE_FLAT_C2.entity_id, "away_mode": True},
        blocking=True,
    )

    # Absence end is now + 365 days; the frozen 12:00 UTC is 05:00 in HA's
    # default test timezone (US/Pacific).
    assert_commands_call(
        mock_client,
        device_url=DHW_CE_FLAT_C2.device_url,
        commands=[
            (
                "setAbsenceStartDate",
                [
                    {
                        "year": 2026,
                        "month": 5,
                        "day": 28,
                        "hour": 5,
                        "minute": 0,
                        "second": 0,
                        "weekday": 3,
                    }
                ],
            ),
            (
                "setAbsenceEndDate",
                [
                    {
                        "year": 2027,
                        "month": 5,
                        "day": 28,
                        "hour": 5,
                        "minute": 0,
                        "second": 0,
                        "weekday": 4,
                    }
                ],
            ),
            ("setAbsenceMode", ["prog"]),
        ],
    )


async def test_turn_away_mode_off(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Turning away mode off sends setAbsenceMode['off']."""
    await setup_overkiz_integration(fixture=DHW_CE_FLAT_C2.fixture)

    await hass.services.async_call(
        "water_heater",
        "set_away_mode",
        {"entity_id": DHW_CE_FLAT_C2.entity_id, "away_mode": False},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=DHW_CE_FLAT_C2.device_url,
        command_name="setAbsenceMode",
        parameters=["off"],
    )


async def test_set_temperature(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test setting the target temperature emits setTargetTemperature then a refresh."""
    await setup_overkiz_integration(fixture=DHW_CE_FLAT_C2.fixture)

    await hass.services.async_call(
        "water_heater",
        "set_temperature",
        {"entity_id": DHW_CE_FLAT_C2.entity_id, ATTR_TEMPERATURE: 55.0},
        blocking=True,
    )

    assert mock_client.execute_action_group.await_count == 2
    first = mock_client.execute_action_group.await_args_list[0].kwargs["actions"]
    second = mock_client.execute_action_group.await_args_list[1].kwargs["actions"]
    assert first[0].device_url == DHW_CE_FLAT_C2.device_url
    assert first[0].commands[0].name == "setTargetTemperature"
    assert first[0].commands[0].parameters == [55.0]
    assert second[0].commands[0].name == "refreshWaterTargetTemperature"


async def test_set_operation_mode_auto(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test selecting 'auto' sets DHW mode to autoMode."""
    await setup_overkiz_integration(fixture=DHW_CE_FLAT_C2.fixture)

    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {"entity_id": DHW_CE_FLAT_C2.entity_id, ATTR_OPERATION_MODE: "auto"},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=DHW_CE_FLAT_C2.device_url,
        command_name="setDHWMode",
        parameters=["autoMode"],
    )


async def test_set_operation_mode_performance_turns_boost_on(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test selecting 'performance' refreshes boost dates then sets boost on."""
    await setup_overkiz_integration(fixture=DHW_CE_FLAT_C2.fixture)

    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {"entity_id": DHW_CE_FLAT_C2.entity_id, ATTR_OPERATION_MODE: STATE_PERFORMANCE},
        blocking=True,
    )

    assert_commands_call(
        mock_client,
        device_url=DHW_CE_FLAT_C2.device_url,
        commands=[
            ("refreshBoostStartDate", None),
            ("refreshBoostEndDate", None),
            ("setBoostMode", ["on"]),
        ],
    )


async def test_current_operation_reports_performance_when_boost_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test current_operation reports performance when boost mode turns on."""
    await setup_overkiz_integration(fixture=DHW_CE_FLAT_C2.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=DHW_CE_FLAT_C2.device_url,
                device_states=[
                    {
                        "name": OverkizState.IO_DHW_BOOST_MODE,
                        "type": 3,
                        "value": "on",
                    }
                ],
            )
        ],
    )

    state = hass.states.get(DHW_CE_FLAT_C2.entity_id)
    assert state is not None
    assert state.attributes[ATTR_OPERATION_MODE] == STATE_PERFORMANCE


# --- Hitachi Yutaki DHW (modbus:YutakiV2DHWTComponent) ---
async def test_hitachi_turn_on_uses_run(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test turning on from off sends setControlDHW['run'] then setDHWMode."""
    await setup_overkiz_integration(fixture=DHW_HITACHI_YUTAKI.fixture)

    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {"entity_id": DHW_HITACHI_YUTAKI.entity_id, ATTR_OPERATION_MODE: STATE_ON},
        blocking=True,
    )

    assert_commands_call(
        mock_client,
        device_url=DHW_HITACHI_YUTAKI.device_url,
        commands=[
            ("setControlDHW", ["run"]),
            ("setDHWMode", ["standard"]),
        ],
    )


async def test_hitachi_turn_off_uses_stop(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test turning off sends setControlDHW['stop']."""
    await setup_overkiz_integration(fixture=DHW_HITACHI_YUTAKI.fixture)

    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {"entity_id": DHW_HITACHI_YUTAKI.entity_id, ATTR_OPERATION_MODE: STATE_OFF},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=DHW_HITACHI_YUTAKI.device_url,
        command_name="setControlDHW",
        parameters=["stop"],
    )
