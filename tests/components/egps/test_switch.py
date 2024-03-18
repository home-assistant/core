"""Test the switch functionality."""

from collections.abc import Callable, Generator
from unittest.mock import MagicMock, patch

from pyegps.exceptions import EgpsException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.egps.const import DOMAIN
from homeassistant.components.homeassistant import (
    DOMAIN as HOME_ASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_get_device")
def patch_get_device(pyegps_device_mock: MagicMock) -> Generator[MagicMock, None, None]:
    """Fixture to patch the `get_device` api method."""
    with patch(
        "homeassistant.components.egps.get_device", return_value=pyegps_device_mock
    ) as mock:
        yield mock


async def test_switch_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    valid_config_entry: MockConfigEntry,
    mock_get_device: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a successful setup of device switches."""

    entry = valid_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    switches = [entry for entry in entries if entry.domain == Platform.SWITCH]
    assert len(switches) == 4

    switch = switches[0]
    assert switch == snapshot

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def _test_switch_on_off(
    hass: HomeAssistant, entity_id: str, dev: MagicMock
) -> None:
    """Call switch on/off service."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == STATE_OFF


async def _test_switch_on_exeception(
    hass: HomeAssistant, entity_id: str, dev: MagicMock
) -> None:
    """Call switch on service with USBError side effect."""
    dev.switch_on.side_effect = EgpsException
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            HOME_ASSISTANT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": entity_id},
            blocking=True,
        )

    dev.switch_on.side_effect = None


async def _test_switch_off_exeception(
    hass: HomeAssistant, entity_id: str, dev: MagicMock
) -> None:
    """Call switch off service with USBError side effect."""
    dev.switch_off.side_effect = EgpsException
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {"entity_id": entity_id},
            blocking=True,
        )
    dev.switch_off.side_effect = None


async def _test_switch_update_exception(
    hass: HomeAssistant, entity_id: str, dev: MagicMock
) -> None:
    """Call switch off service with USBError side effect."""
    dev.get_status.side_effect = EgpsException
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {"entity_id": entity_id},
            blocking=True,
        )
    dev.get_status.side_effect = None


@pytest.mark.parametrize(
    "test_function",
    [
        _test_switch_on_off,
        _test_switch_on_exeception,
        _test_switch_off_exeception,
        _test_switch_update_exception,
    ],
)
async def test_switch_services(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    valid_config_entry: MockConfigEntry,
    mock_get_device: MagicMock,
    test_function: Callable,
) -> None:
    """Test a successful setup of device switches."""

    entry = valid_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    switches = [entry for entry in entries if entry.domain == Platform.SWITCH]

    switch = switches[0]
    device_mock = mock_get_device.return_value
    await test_function(hass, switch.entity_id, device_mock)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
