"""Test switches for ToGrill integration."""

from unittest.mock import Mock, patch

from habluetooth import BluetoothServiceInfoBleak
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.togrill.const import (
    CONF_ACTIVE_BY_DEFAULT,
    DOMAIN,
    MAJOR_VERSION,
    MINOR_VERSION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    TOGRILL_MOCK_ENTRY_DATA,
    TOGRILL_MOCK_ENTRY_OPTIONS,
    TOGRILL_SERVICE_INFO,
    setup_entry,
)

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.fixture
def mock_entry_non_active() -> MockConfigEntry:
    """Create hass config fixture with non default activation."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=TOGRILL_MOCK_ENTRY_DATA,
        options={**TOGRILL_MOCK_ENTRY_OPTIONS, CONF_ACTIVE_BY_DEFAULT: False},
        unique_id=TOGRILL_SERVICE_INFO.address,
        version=MAJOR_VERSION,
        minor_version=MINOR_VERSION,
    )


def patch_async_ble_device_from_address(
    return_value: BluetoothServiceInfoBleak | None = None,
):
    """Patch async_ble_device_from_address to return a mocked BluetoothServiceInfoBleak."""
    return patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=return_value,
    )


async def test_setup_available(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
) -> None:
    """Test the switches."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.SWITCH])

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


async def test_setup_not_available(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
) -> None:
    """Test the switches."""

    await setup_entry(hass, mock_entry, [Platform.SWITCH])

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


async def test_turn_on(
    hass: HomeAssistant,
    mock_entry_non_active: MockConfigEntry,
    mock_client: Mock,
    mock_client_class: Mock,
) -> None:
    """Test the switch set."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry_non_active, [Platform.SWITCH])

    entity_id = "switch.pro_05_control_active"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        target={
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"

    mock_client_class.connect.assert_called_once()


async def test_turn_off(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
) -> None:
    """Test the switch set."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.SWITCH])

    entity_id = "switch.pro_05_control_active"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        target={
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"

    mock_client.disconnect.assert_called_once()


async def test_device_disconnected(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
) -> None:
    """Test the switch set."""
    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.SWITCH])

    entity_id = "switch.pro_05_control_active"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"

    with patch_async_ble_device_from_address():
        mock_client.mocked_disconnected_callback()
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"


async def test_device_discovered(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
) -> None:
    """Test the switch set."""

    await setup_entry(hass, mock_entry, [Platform.SWITCH])

    entity_id = "switch.pro_05_control_active"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"
