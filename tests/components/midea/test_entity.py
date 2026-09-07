"""Tests for midea entity behavior via loaded platforms."""

from collections.abc import Callable

from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.exceptions import SocketException
import pytest

from homeassistant.components.midea.const import DOMAIN
from homeassistant.components.midea.entity import midea_api_call
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import DummyDevice, default_ac_device, entity_entries
from .const import TEST_DEVICE_ID, TEST_MAC_ADDRESS, TEST_MODEL, TEST_SERIAL_NUMBER

from tests.common import MockConfigEntry


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
async def test_entity_updates_from_device_callback(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
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


async def test_entity_callback_ignored_while_hass_stopping(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test update callback does not schedule updates while Home Assistant stops."""
    device = default_ac_device()
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

    assert hass.states.get(entity_entry.entity_id) is not None

    device.attributes[ACAttributes.indoor_temperature] = 25.0
    hass.set_state(CoreState.stopping)
    device.notify_update({"available": True})
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.attributes["current_temperature"] == 21.0
