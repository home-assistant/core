"""Test Velux number entities."""

from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pyvlx import Intensity, PyVLXException
from pyvlx.opening_device import Position

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.velux.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import update_callback_entity, update_polled_entities

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform

pytestmark = pytest.mark.usefixtures("setup_integration")


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform to test."""
    return Platform.NUMBER


def get_number_entity_id(mock: AsyncMock) -> str:
    """Helper to get the entity ID for a given mock node."""
    return f"number.{mock.name.lower().replace(' ', '_')}"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the entity and validate registry metadata."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


async def test_heating_entity_number_device_association(
    hass: HomeAssistant,
    mock_exterior_heating: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Ensure exterior heating number entity is associated with a device."""
    entity_id = get_number_entity_id(mock_exterior_heating)

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.device_id is not None
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry is not None
    assert (DOMAIN, mock_exterior_heating.serial_number) in device_entry.identifiers


async def test_get_intensity(
    hass: HomeAssistant,
    mock_exterior_heating: AsyncMock,
) -> None:
    """Entity state follows intensity value and becomes unknown when not known."""
    entity_id = get_number_entity_id(mock_exterior_heating)

    # Set initial intensity values
    mock_exterior_heating.intensity.intensity_percent = 20
    await update_callback_entity(hass, mock_exterior_heating)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "20"

    mock_exterior_heating.intensity.known = False
    await update_callback_entity(hass, mock_exterior_heating)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_set_value_sets_intensity(
    hass: HomeAssistant,
    mock_exterior_heating: AsyncMock,
) -> None:
    """Calling set_value forwards to set_intensity."""
    entity_id = get_number_entity_id(mock_exterior_heating)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 30, "entity_id": entity_id},
        blocking=True,
    )

    mock_exterior_heating.set_intensity.assert_awaited_once()
    args, kwargs = mock_exterior_heating.set_intensity.await_args
    intensity = args[0]
    assert isinstance(intensity, Intensity)
    assert intensity.intensity_percent == 30
    assert kwargs.get("wait_for_completion") is True


async def test_set_invalid_value_fails(
    hass: HomeAssistant,
    mock_exterior_heating: AsyncMock,
) -> None:
    """Values outside valid range raise ServiceValidationError."""
    entity_id = get_number_entity_id(mock_exterior_heating)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 101, "entity_id": entity_id},
            blocking=True,
        )

    mock_exterior_heating.set_intensity.assert_not_awaited()


# helpers for limitation entity IDs
def closed_limit_entity_id(mock: AsyncMock) -> str:
    """Return entity ID of the closed position limit entity."""
    return f"number.{mock.name.lower().replace(' ', '_')}_closed_position_limit"


def open_limit_entity_id(mock: AsyncMock) -> str:
    """Return entity ID of the open position limit entity."""
    return f"number.{mock.name.lower().replace(' ', '_')}_open_position_limit"


async def test_limitation_entity_number_device_association(
    hass: HomeAssistant,
    mock_window: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Ensure limitation number entity is associated with a device."""
    entity_id = closed_limit_entity_id(mock_window)

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.device_id is not None
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry is not None
    assert (DOMAIN, mock_window.serial_number) in device_entry.identifiers


@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
async def test_limitation_entities_created(
    hass: HomeAssistant,
    mock_window: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Open and closed position limit entities are created disabled by default."""
    for get_entity_id in (closed_limit_entity_id, open_limit_entity_id):
        entry = entity_registry.async_get(get_entity_id(mock_window))
        assert entry is not None
        assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_limitation_entities_enabled_state(
    hass: HomeAssistant,
    mock_window: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After enabling, open/closed limit entities reflect HA-side opening semantics."""
    # HA minimum opening comes from pyvlx max, HA maximum opening comes from pyvlx min.
    mock_window.get_limitation_min.return_value = MagicMock(position_percent=0)
    mock_window.get_limitation_max.return_value = MagicMock(position_percent=100)
    await update_polled_entities(hass, freezer)

    assert hass.states.get(closed_limit_entity_id(mock_window)).state == "0"
    assert hass.states.get(open_limit_entity_id(mock_window)).state == "100"

    mock_window.get_limitation_min.return_value = MagicMock(position_percent=50)
    mock_window.get_limitation_max.return_value = MagicMock(position_percent=30)
    await update_polled_entities(hass, freezer)

    assert hass.states.get(closed_limit_entity_id(mock_window)).state == "70"
    assert hass.states.get(open_limit_entity_id(mock_window)).state == "50"


@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_min_limitation(
    hass: HomeAssistant,
    mock_window: AsyncMock,
) -> None:
    """Setting HA minimum opening updates pyvlx max and preserves pyvlx min."""
    entity_id = closed_limit_entity_id(mock_window)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 40, "entity_id": entity_id},
        blocking=True,
    )

    mock_window.set_position_limitations.assert_awaited_once_with(
        position_min=mock_window.get_limitation_min.return_value,
        position_max=Position(position_percent=60),
    )


@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_limitation_updates_state_optimistically(
    hass: HomeAssistant,
    mock_window: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Setting a limitation updates the entity state before the next refresh."""
    mock_window.get_limitation_min.return_value = MagicMock(position_percent=0)
    mock_window.get_limitation_max.return_value = MagicMock(position_percent=100)
    await update_polled_entities(hass, freezer)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 40, "entity_id": closed_limit_entity_id(mock_window)},
        blocking=True,
    )

    assert hass.states.get(closed_limit_entity_id(mock_window)).state == "40"


@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_max_limitation(
    hass: HomeAssistant,
    mock_window: AsyncMock,
) -> None:
    """Setting HA maximum opening updates pyvlx min and preserves pyvlx max."""
    entity_id = open_limit_entity_id(mock_window)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 70, "entity_id": entity_id},
        blocking=True,
    )

    mock_window.set_position_limitations.assert_awaited_once_with(
        position_min=Position(position_percent=30),
        position_max=mock_window.get_limitation_max.return_value,
    )


@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_limitation_unavailable_on_error(
    hass: HomeAssistant,
    mock_window: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entities become unavailable when pyvlx raises an exception."""
    mock_window.get_limitation_min.side_effect = PyVLXException("Connection lost")
    mock_window.get_limitation_max.side_effect = PyVLXException("Connection lost")
    await update_polled_entities(hass, freezer)

    assert (
        hass.states.get(closed_limit_entity_id(mock_window)).state == STATE_UNAVAILABLE
    )
    assert hass.states.get(open_limit_entity_id(mock_window)).state == STATE_UNAVAILABLE

    # Recovery
    mock_window.get_limitation_min.side_effect = None
    mock_window.get_limitation_min.return_value = MagicMock(position_percent=0)
    mock_window.get_limitation_max.side_effect = None
    mock_window.get_limitation_max.return_value = MagicMock(position_percent=0)
    await update_polled_entities(hass, freezer)

    assert (
        hass.states.get(closed_limit_entity_id(mock_window)).state != STATE_UNAVAILABLE
    )
    assert hass.states.get(open_limit_entity_id(mock_window)).state != STATE_UNAVAILABLE
