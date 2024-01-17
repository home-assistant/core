"""Tests for the La Marzocco number entities."""


from unittest.mock import MagicMock

from lmcloud.const import LaMarzoccoModel
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_coffee_boiler(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco coffee temperature Number."""
    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"number.{serial_number}_coffee_target_temperature")

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
            ATTR_ENTITY_ID: f"number.{serial_number}_coffee_target_temperature",
            ATTR_VALUE: 95,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_coffee_temp.mock_calls) == 1
    mock_lamarzocco.set_coffee_temp.assert_called_once_with(temperature=95)


@pytest.mark.parametrize(
    "device_fixture", [LaMarzoccoModel.GS3_AV, LaMarzoccoModel.GS3_MP]
)
@pytest.mark.parametrize(
    ("entity_name", "value", "func_name", "kwargs"),
    [
        ("steam_target_temperature", 131, "set_steam_temp", {"temperature": 131}),
        ("tea_water_duration", 15, "set_dose_hot_water", {"value": 15}),
    ],
)
async def test_gs3_exclusive(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    entity_name: str,
    value: float,
    func_name: str,
    kwargs: dict[str, float],
) -> None:
    """Test exclusive entities for GS3 AV/MP."""

    serial_number = mock_lamarzocco.serial_number

    func = getattr(mock_lamarzocco, func_name)

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

    assert len(func.mock_calls) == 1
    func.assert_called_once_with(**kwargs)


@pytest.mark.parametrize(
    "device_fixture", [LaMarzoccoModel.LINEA_MICRA, LaMarzoccoModel.LINEA_MINI]
)
async def test_gs3_exclusive_none(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Ensure GS3 exclusive is None for unsupported models."""

    ENTITIES = ("steam_target_temperature", "tea_water_duration")

    serial_number = mock_lamarzocco.serial_number
    for entity in ENTITIES:
        state = hass.states.get(f"number.{serial_number}_{entity}")
        assert state is None
