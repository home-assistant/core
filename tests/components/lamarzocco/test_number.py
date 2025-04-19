"""Tests for the La Marzocco number entities."""

from typing import Any
from unittest.mock import MagicMock

from pylamarzocco.const import (
    ModelName,
    PreExtractionMode,
    SmartStandByType,
    WidgetType,
)
from pylamarzocco.exceptions import RequestNotSuccessful
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entity_name", "value", "func_name", "kwargs"),
    [
        (
            "coffee_target_temperature",
            94,
            "set_coffee_target_temperature",
            {"temperature": 94},
        ),
        (
            "smart_standby_time",
            23,
            "set_smart_standby",
            {"enabled": True, "mode": SmartStandByType.POWER_ON, "minutes": 23},
        ),
    ],
)
async def test_general_numbers(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    entity_name: str,
    value: float,
    func_name: str,
    kwargs: dict[str, Any],
) -> None:
    """Test the numbers available to all machines."""

    await async_init_integration(hass, mock_config_entry)
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"number.{serial_number}_{entity_name}")

    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device

    # service call
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: f"number.{serial_number}_{entity_name}",
            ATTR_VALUE: value,
        },
        blocking=True,
    )

    mock_func = getattr(mock_lamarzocco, func_name)
    mock_func.assert_called_once_with(**kwargs)


@pytest.mark.parametrize("device_fixture", [ModelName.LINEA_MICRA])
async def test_preinfusion(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test preinfusion number."""

    await async_init_integration(hass, mock_config_entry)
    serial_number = mock_lamarzocco.serial_number
    entity_id = f"number.{serial_number}_preinfusion_time"

    state = hass.states.get(entity_id)

    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    # service call
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: 5.3,
        },
        blocking=True,
    )

    mock_lamarzocco.set_pre_extraction_times.assert_called_once_with(
        seconds_off=5.3,
        seconds_on=0,
    )


@pytest.mark.parametrize("device_fixture", [ModelName.LINEA_MICRA])
async def test_prebrew_on(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test prebrew on number."""

    mock_lamarzocco.dashboard.config[
        WidgetType.CM_PRE_BREWING
    ].mode = PreExtractionMode.PREBREWING

    await async_init_integration(hass, mock_config_entry)
    serial_number = mock_lamarzocco.serial_number
    entity_id = f"number.{serial_number}_prebrew_on_time"

    state = hass.states.get(entity_id)

    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    # service call
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: 5.3,
        },
        blocking=True,
    )

    mock_lamarzocco.set_pre_extraction_times.assert_called_once_with(
        seconds_on=5.3,
        seconds_off=mock_lamarzocco.dashboard.config[WidgetType.CM_PRE_BREWING]
        .times.pre_brewing[0]
        .seconds.seconds_out,
    )


@pytest.mark.parametrize("device_fixture", [ModelName.LINEA_MICRA])
async def test_prebrew_off(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test prebrew off number."""
    mock_lamarzocco.dashboard.config[
        WidgetType.CM_PRE_BREWING
    ].mode = PreExtractionMode.PREBREWING

    await async_init_integration(hass, mock_config_entry)
    serial_number = mock_lamarzocco.serial_number
    entity_id = f"number.{serial_number}_prebrew_off_time"

    state = hass.states.get(entity_id)

    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    # service call
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: 7,
        },
        blocking=True,
    )

    mock_lamarzocco.set_pre_extraction_times.assert_called_once_with(
        seconds_off=7,
        seconds_on=mock_lamarzocco.dashboard.config[WidgetType.CM_PRE_BREWING]
        .times.pre_brewing[0]
        .seconds.seconds_in,
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_error(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test number entities raise error on service call."""
    await async_init_integration(hass, mock_config_entry)
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"number.{serial_number}_coffee_target_temperature")
    assert state

    mock_lamarzocco.set_coffee_target_temperature.side_effect = RequestNotSuccessful(
        "Boom"
    )
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: f"number.{serial_number}_coffee_target_temperature",
                ATTR_VALUE: 94,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "number_exception"
