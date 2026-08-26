"""Tests for midea button.py."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.devices.e1 import DeviceAttributes as E1Attributes
from midealocal.exceptions import ValueWrongType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DummyDevice, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform


def _e1_device(*, model: str = "7600024L") -> DummyDevice:
    device = DummyDevice(
        DeviceType.E1,
        attributes={
            E1Attributes.power: True,
            E1Attributes.mode: "auto_wash",
        },
    )
    device.model = model
    return device


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_button_state_snapshot(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test async_setup_entry creates the start button for a supported E1 dishwasher."""
    device = _e1_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry, device)

        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_button_press_starts_dishwasher(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test pressing the button calls start_work on the device."""
    device = _e1_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_start"]

    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state != "unavailable"

    device.calls.clear()
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_entry.entity_id},
        blocking=True,
    )
    assert device.calls == [("start_work",)]


async def test_button_press_raises_when_device_off(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test pressing the button while the dishwasher is off raises a clear error."""
    device = _e1_device()
    device.attributes[E1Attributes.power] = False
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_start"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state != "unavailable"

    device.calls.clear()
    with pytest.raises(ServiceValidationError, match="Turn on the dishwasher"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_entry.entity_id},
            blocking=True,
        )
    assert device.calls == []


async def test_button_unavailable_when_device_offline(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test the button follows base device availability, even with a mode selected."""
    device = _e1_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_start"]
    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state != "unavailable"

    device.available = False
    device.notify_update({"available": False})
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "unavailable"


async def test_button_not_created_for_unsupported_model(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no button is created for an E1 device with an unsupported model."""
    device = _e1_device(model="some-other-model")
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_button_not_created_for_other_device_type(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no button is created for a device type other than E1."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
        },
    )
    device.model = "7600024L"
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_button_press_raises_on_device_communication_error(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a device communication failure surfaces as a HomeAssistantError."""
    device = _e1_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_start"]

    with (
        patch.object(device, "start_work", side_effect=ValueWrongType("no mode")),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_entry.entity_id},
            blocking=True,
        )
