"""Test the V2C photovoltaic automation blueprint."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_mock_service

from homeassistant.components import v2c
from homeassistant.components.v2c.const import CONF_PV_AVAILABLE, DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.components.automation.test_blueprint import patch_blueprint

MODE = "select.evse_1_1_1_1_dynamic_power_mode"
CONTRACTED_POWER = "input_number.contracted_power"
PV_BALANCE = "input_number.pv_balance"
BLUEPRINT_PATH = "v2c/contracted_power.yaml"
BLUEPRINT_FILE = (
    Path(v2c.__file__).parent / "blueprints/automation/contracted_power.yaml"
)


@pytest.fixture
async def setup_blueprint(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_v2c_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> tuple[list[ServiceCall], str]:
    """Set up the charger and an automation using the blueprint."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_PV_AVAILABLE: True}
    )
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    calls = async_mock_service(hass, DOMAIN, "set_contracted_power")
    hass.states.async_set(CONTRACTED_POWER, "4600", {"unit_of_measurement": "W"})
    hass.states.async_set(PV_BALANCE, "-500", {"unit_of_measurement": "W"})
    with patch_blueprint(BLUEPRINT_PATH, BLUEPRINT_FILE):
        assert await async_setup_component(
            hass,
            "automation",
            {
                "automation": {
                    "use_blueprint": {
                        "path": BLUEPRINT_PATH,
                        "input": {
                            "mode_entity": MODE,
                            "contracted_power": CONTRACTED_POWER,
                            "pv_balance": PV_BALANCE,
                        },
                    }
                }
            },
        )
    await hass.async_block_till_done()
    return calls, device.id


@pytest.mark.parametrize(
    ("entity_id", "value", "expected_power"),
    [
        pytest.param(CONTRACTED_POWER, "5700", 5700, id="grid-helper"),
        pytest.param(MODE, "pv_exclusive", -500, id="pv-mode"),
        pytest.param(MODE, "pv_grid", 4600, id="grid-mode"),
        pytest.param(MODE, "stop", 4600, id="stop-mode"),
    ],
)
async def test_changes(
    hass: HomeAssistant,
    setup_blueprint: tuple[list[ServiceCall], str],
    entity_id: str,
    value: str,
    expected_power: int,
) -> None:
    """Test the active value is applied after relevant changes."""
    calls, device_id = setup_blueprint
    hass.states.async_set(entity_id, value, {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data == {"device_id": device_id, "power": expected_power}


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        pytest.param(PV_BALANCE, "-300", id="inactive-pv-helper"),
        pytest.param(MODE, "profile", id="profile-mode"),
        pytest.param(MODE, "unavailable", id="unavailable-mode"),
    ],
)
async def test_changes_not_applied(
    hass: HomeAssistant,
    setup_blueprint: tuple[list[ServiceCall], str],
    entity_id: str,
    value: str,
) -> None:
    """Test inactive helpers and unsupported modes do not write power."""
    calls, _ = setup_blueprint
    hass.states.async_set(entity_id, value, {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    assert not calls


async def test_pv_helper_change(
    hass: HomeAssistant, setup_blueprint: tuple[list[ServiceCall], str]
) -> None:
    """Test PV balance changes apply only in PV-exclusive mode."""
    calls, device_id = setup_blueprint
    hass.states.async_set(MODE, "pv_exclusive")
    await hass.async_block_till_done()
    calls.clear()

    hass.states.async_set(PV_BALANCE, "-0.3", {"unit_of_measurement": "kW"})
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data == {"device_id": device_id, "power": -300}


async def test_grid_helper_change_in_pv_mode(
    hass: HomeAssistant, setup_blueprint: tuple[list[ServiceCall], str]
) -> None:
    """Test peak and valley changes do not overwrite the PV balance."""
    calls, _ = setup_blueprint
    hass.states.async_set(MODE, "pv_exclusive")
    await hass.async_block_till_done()
    calls.clear()

    hass.states.async_set(CONTRACTED_POWER, "6900", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    assert not calls


async def test_queued_changes_use_latest_state(
    hass: HomeAssistant, setup_blueprint: tuple[list[ServiceCall], str]
) -> None:
    """Test queued updates do not apply a stale value after a mode change."""
    _, device_id = setup_blueprint
    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[ServiceCall] = []

    async def set_power(call: ServiceCall) -> None:
        calls.append(call)
        started.set()
        await release.wait()

    hass.services.async_register(DOMAIN, "set_contracted_power", set_power)
    hass.states.async_set(CONTRACTED_POWER, "5700", {"unit_of_measurement": "W"})
    await asyncio.wait_for(started.wait(), 5)
    hass.states.async_set(MODE, "pv_exclusive")
    hass.states.async_set(PV_BALANCE, "-300", {"unit_of_measurement": "W"})
    release.set()
    await hass.async_block_till_done()

    assert [call.data for call in calls] == [
        {"device_id": device_id, "power": 5700},
        {"device_id": device_id, "power": -300},
        {"device_id": device_id, "power": -300},
    ]


@pytest.mark.parametrize(
    ("value", "unit"),
    [("unavailable", "W"), ("unknown", "W"), ("4600", "V"), ("abc", "W")],
)
async def test_invalid_helper(
    hass: HomeAssistant,
    setup_blueprint: tuple[list[ServiceCall], str],
    value: str,
    unit: str,
) -> None:
    """Test invalid helper values and units are not sent to the charger."""
    calls, _ = setup_blueprint
    hass.states.async_set(CONTRACTED_POWER, value, {"unit_of_measurement": unit})
    await hass.async_block_till_done()
    assert not calls


async def test_startup(
    hass: HomeAssistant, setup_blueprint: tuple[list[ServiceCall], str]
) -> None:
    """Test the active helper is applied after Home Assistant starts."""
    calls, device_id = setup_blueprint
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data == {"device_id": device_id, "power": 4600}


async def test_manual_run(
    hass: HomeAssistant, setup_blueprint: tuple[list[ServiceCall], str]
) -> None:
    """Test a manual run applies the currently active helper."""
    calls, device_id = setup_blueprint
    await hass.services.async_call(
        "automation",
        "trigger",
        {"entity_id": "automation.automation_0"},
        blocking=True,
    )
    assert len(calls) == 1
    assert calls[0].data == {"device_id": device_id, "power": 4600}
