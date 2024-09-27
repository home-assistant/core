"""Tests for La Marzocco switches."""

from unittest.mock import MagicMock

from lmcloud.exceptions import RequestNotSuccessful
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import WAKE_UP_SLEEP_ENTRY_IDS, async_init_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    (
        "entity_name",
        "method_name",
    ),
    [
        (
            "",
            "set_power",
        ),
        (
            "_steam_boiler",
            "set_steam",
        ),
    ],
)
async def test_switches(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_name: str,
    method_name: str,
) -> None:
    """Test the La Marzocco switches."""
    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    control_fn = getattr(mock_lamarzocco, method_name)

    state = hass.states.get(f"switch.{serial_number}{entity_name}")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}{entity_name}",
        },
        blocking=True,
    )

    assert len(control_fn.mock_calls) == 1
    control_fn.assert_called_once_with(False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"switch.{serial_number}{entity_name}",
        },
        blocking=True,
    )

    assert len(control_fn.mock_calls) == 2
    control_fn.assert_called_with(True)


async def test_device(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device for one switch."""

    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get(f"switch.{mock_lamarzocco.serial_number}")
    assert state

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot


async def test_auto_on_off_switches(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the auto on off/switches."""

    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    for wake_up_sleep_entry_id in WAKE_UP_SLEEP_ENTRY_IDS:
        state = hass.states.get(
            f"switch.{serial_number}_auto_on_off_{wake_up_sleep_entry_id}"
        )
        assert state
        assert state == snapshot(name=f"state.auto_on_off_{wake_up_sleep_entry_id}")

        entry = entity_registry.async_get(state.entity_id)
        assert entry
        assert entry == snapshot(name=f"entry.auto_on_off_{wake_up_sleep_entry_id}")

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: f"switch.{serial_number}_auto_on_off_{wake_up_sleep_entry_id}",
            },
            blocking=True,
        )

        wake_up_sleep_entry = mock_lamarzocco.config.wake_up_sleep_entries[
            wake_up_sleep_entry_id
        ]
        wake_up_sleep_entry.enabled = False

        mock_lamarzocco.set_wake_up_sleep.assert_called_with(wake_up_sleep_entry)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: f"switch.{serial_number}_auto_on_off_{wake_up_sleep_entry_id}",
            },
            blocking=True,
        )
        wake_up_sleep_entry.enabled = True
        mock_lamarzocco.set_wake_up_sleep.assert_called_with(wake_up_sleep_entry)


async def test_switch_exceptions(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco switches."""
    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"switch.{serial_number}")
    assert state

    mock_lamarzocco.set_power.side_effect = RequestNotSuccessful("Boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: f"switch.{serial_number}",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "switch_off_error"

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: f"switch.{serial_number}",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "switch_on_error"

    state = hass.states.get(f"switch.{serial_number}_auto_on_off_os2oswx")
    assert state

    mock_lamarzocco.set_wake_up_sleep.side_effect = RequestNotSuccessful("Boom")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: f"switch.{serial_number}_auto_on_off_os2oswx",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "auto_on_off_error"
