"""Tests for midea entity behavior via loaded platforms."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.exceptions import SocketException
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.midea.const import DOMAIN
from homeassistant.components.midea.entity import MideaEntity, midea_api_call
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import DummyDevice, default_ac_device, entity_entries
from .const import TEST_DEVICE_ID, TEST_MAC_ADDRESS, TEST_MODEL, TEST_SERIAL_NUMBER


def test_midea_api_call_translates_midea_local_error() -> None:
    """Test midea_api_call turns a midealocal error into a HomeAssistantError."""
    with pytest.raises(HomeAssistantError) as exc_info, midea_api_call():
        raise SocketException("offline")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "device_communication_error"
    assert exc_info.value.translation_placeholders == {"error": "offline"}


@pytest.mark.parametrize(
    (
        "update",
        "status",
        "availability",
        "expected_current_temp",
        "expected_unavailable",
    ),
    [
        pytest.param(
            {ACAttributes.indoor_temperature: 24.0},
            {"available": True},
            True,
            24.0,
            False,
            id="temperature_update",
        ),
        pytest.param(
            {},
            {"available": False},
            False,
            None,
            True,
            id="availability_update",
        ),
        pytest.param(
            {ACAttributes.indoor_temperature: 24.0},
            {"power": True, ACAttributes.indoor_temperature: 24.0},
            True,
            24.0,
            False,
            id="attribute_update_without_available_key",
        ),
    ],
)
@pytest.mark.parametrize(
    "hass_state",
    [
        pytest.param(CoreState.starting, id="starting"),
        pytest.param(CoreState.running, id="running"),
    ],
)
async def test_entity_updates_from_device_callback(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    hass_state: CoreState,
    update: dict[str, float],
    status: dict[str, bool | float],
    availability: bool,
    expected_current_temp: float | None,
    expected_unavailable: bool,
) -> None:
    """Test entity callback updates state and availability."""
    device = default_ac_device()
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.attributes["current_temperature"] == 21.0
    assert state.state != "unavailable"

    hass.set_state(hass_state)
    device.attributes.update(update)
    device.available = availability
    device.notify_update(status)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.attributes.get("current_temperature") == expected_current_temp
    assert (state.state == "unavailable") is expected_unavailable


@pytest.mark.parametrize(
    ("mac", "serial_number", "expected_connections", "expected_serial_number"),
    [
        pytest.param(
            TEST_MAC_ADDRESS,
            TEST_SERIAL_NUMBER,
            {(dr.CONNECTION_NETWORK_MAC, TEST_MAC_ADDRESS)},
            TEST_SERIAL_NUMBER,
            id="populated",
        ),
        pytest.param(
            "",
            "",
            set(),
            None,
            id="absent",
        ),
    ],
)
async def test_device_info_optional_metadata(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    mac: str,
    serial_number: str,
    expected_connections: set[tuple[str, str]],
    expected_serial_number: str | None,
) -> None:
    """Test device registry entry reflects optional mac and serial number."""
    device = default_ac_device()
    device.mac = mac
    device.serial_number = serial_number
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)

    assert (
        device_entry := device_registry.async_get_device_by_identifier(
            (DOMAIN, str(TEST_DEVICE_ID)), config_entry.entry_id
        )
    ) is not None

    assert device_entry.model_id == device.device_type.name
    assert device_entry.hw_version == TEST_MODEL
    assert device_entry.connections == expected_connections
    assert device_entry.serial_number == expected_serial_number


@pytest.mark.parametrize(
    "hass_state",
    [
        pytest.param(CoreState.not_running, id="not_running"),
        pytest.param(CoreState.stopping, id="stopping"),
        pytest.param(CoreState.final_write, id="final_write"),
        pytest.param(CoreState.stopped, id="stopped"),
    ],
)
async def test_entity_callback_ignored_once_hass_stops(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    hass_state: CoreState,
) -> None:
    """Test update callback does not schedule updates after Home Assistant stops."""
    device = default_ac_device()
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

    assert hass.states.get(entity_entry.entity_id) is not None

    device.attributes[ACAttributes.indoor_temperature] = 25.0
    hass.set_state(hass_state)
    device.notify_update({"available": True})
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.attributes["current_temperature"] == 21.0


async def test_entity_callback_ignored_when_loop_closed(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test update callback does not schedule updates after the event loop closed."""
    device = default_ac_device()
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

    assert hass.states.get(entity_entry.entity_id) is not None

    device.attributes[ACAttributes.indoor_temperature] = 25.0
    with (
        patch.object(hass.loop, "is_closed", return_value=True),
        patch.object(MideaEntity, "schedule_update_ha_state") as mock_schedule,
    ):
        device.notify_update({"available": True})
    await hass.async_block_till_done()

    mock_schedule.assert_not_called()
    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.attributes["current_temperature"] == 21.0


async def test_entity_callback_while_loop_closes(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a scheduler RuntimeError is swallowed only once the loop is closed."""
    device = default_ac_device()
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

    assert hass.states.get(entity_entry.entity_id) is not None

    loop_closed = False

    def loop_is_closed() -> bool:
        return loop_closed

    def scheduler() -> None:
        nonlocal loop_closed
        loop_closed = True
        raise RuntimeError("Event loop is closed")

    device.attributes[ACAttributes.indoor_temperature] = 25.0
    with (
        patch.object(hass.loop, "is_closed", side_effect=loop_is_closed),
        patch.object(
            MideaEntity, "schedule_update_ha_state", side_effect=scheduler
        ) as mock_schedule,
    ):
        # first callback passes the guard, then the loop closes before the
        # update is scheduled; later callbacks are rejected by the guard
        device.notify_update({"available": True})
        device.notify_update({"available": True})
    await hass.async_block_till_done()

    mock_schedule.assert_called_once_with()
    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.attributes["current_temperature"] == 21.0


async def test_entity_callback_scheduler_runtime_error_propagates(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a scheduler RuntimeError with an open loop is not swallowed."""
    device = default_ac_device()
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

    assert hass.states.get(entity_entry.entity_id) is not None

    device.attributes[ACAttributes.indoor_temperature] = 25.0
    with (
        patch.object(
            MideaEntity,
            "schedule_update_ha_state",
            side_effect=RuntimeError("Unexpected scheduler failure"),
        ),
        pytest.raises(RuntimeError, match="Unexpected scheduler failure"),
    ):
        device.notify_update({"available": True})
