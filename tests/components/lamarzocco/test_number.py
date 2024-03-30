"""Tests for the La Marzocco number entities."""

from unittest.mock import MagicMock

from lmcloud.const import KEYS_PER_MODEL, LaMarzoccoModel
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
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
    mock_lamarzocco.set_coffee_temp.assert_called_once_with(
        temperature=95, ble_device=None
    )


@pytest.mark.parametrize(
    "device_fixture", [LaMarzoccoModel.GS3_AV, LaMarzoccoModel.GS3_MP]
)
@pytest.mark.parametrize(
    ("entity_name", "value", "func_name", "kwargs"),
    [
        (
            "steam_target_temperature",
            131,
            "set_steam_temp",
            {"temperature": 131, "ble_device": None},
        ),
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


@pytest.mark.parametrize(
    "device_fixture", [LaMarzoccoModel.LINEA_MICRA, LaMarzoccoModel.LINEA_MINI]
)
@pytest.mark.parametrize(
    ("entity_name", "value", "kwargs"),
    [
        ("prebrew_off_time", 6, {"on_time": 3000, "off_time": 6000, "key": 1}),
        ("prebrew_on_time", 6, {"on_time": 6000, "off_time": 5000, "key": 1}),
        ("preinfusion_time", 7, {"off_time": 7000, "key": 1}),
    ],
)
async def test_pre_brew_infusion_numbers(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    entity_name: str,
    value: float,
    kwargs: dict[str, float],
) -> None:
    """Test the La Marzocco prebrew/-infusion sensors."""

    mock_lamarzocco.current_status["enable_preinfusion"] = True

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

    assert len(mock_lamarzocco.configure_prebrew.mock_calls) == 1
    mock_lamarzocco.configure_prebrew.assert_called_once_with(**kwargs)


@pytest.mark.parametrize("device_fixture", [LaMarzoccoModel.GS3_AV])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_name", "value", "function_name", "kwargs"),
    [
        (
            "prebrew_off_time",
            6,
            "configure_prebrew",
            {"on_time": 3000, "off_time": 6000},
        ),
        (
            "prebrew_on_time",
            6,
            "configure_prebrew",
            {"on_time": 6000, "off_time": 5000},
        ),
        ("preinfusion_time", 7, "configure_prebrew", {"off_time": 7000}),
        ("dose", 6, "set_dose", {"value": 6}),
    ],
)
async def test_pre_brew_infusion_key_numbers(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    snapshot: SnapshotAssertion,
    entity_name: str,
    value: float,
    function_name: str,
    kwargs: dict[str, float],
) -> None:
    """Test the La Marzocco number sensors for GS3AV model."""

    mock_lamarzocco.current_status["enable_preinfusion"] = True

    serial_number = mock_lamarzocco.serial_number

    func = getattr(mock_lamarzocco, function_name)

    state = hass.states.get(f"number.{serial_number}_{entity_name}")
    assert state is None

    for key in range(1, KEYS_PER_MODEL[mock_lamarzocco.model_name] + 1):
        state = hass.states.get(f"number.{serial_number}_{entity_name}_key_{key}")
        assert state
        assert state == snapshot(name=f"{serial_number}_{entity_name}_key_{key}-state")

        # service call
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: f"number.{serial_number}_{entity_name}_key_{key}",
                ATTR_VALUE: value,
            },
            blocking=True,
        )

        kwargs["key"] = key

        assert len(func.mock_calls) == key
        func.assert_called_with(**kwargs)


@pytest.mark.parametrize("device_fixture", [LaMarzoccoModel.GS3_AV])
async def test_disabled_entites(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test the La Marzocco prebrew/-infusion sensors for GS3AV model."""

    ENTITIES = (
        "prebrew_off_time",
        "prebrew_on_time",
        "preinfusion_time",
        "set_dose",
    )

    serial_number = mock_lamarzocco.serial_number

    for entity_name in ENTITIES:
        for key in range(1, KEYS_PER_MODEL[mock_lamarzocco.model_name] + 1):
            state = hass.states.get(f"number.{serial_number}_{entity_name}_key_{key}")
            assert state is None


@pytest.mark.parametrize(
    "device_fixture",
    [LaMarzoccoModel.GS3_MP, LaMarzoccoModel.LINEA_MICRA, LaMarzoccoModel.LINEA_MINI],
)
async def test_not_existing_key_entites(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Assert not existing key entities."""

    serial_number = mock_lamarzocco.serial_number

    for entity in (
        "prebrew_off_time",
        "prebrew_on_time",
        "preinfusion_time",
        "set_dose",
    ):
        for key in range(1, KEYS_PER_MODEL[LaMarzoccoModel.GS3_AV] + 1):
            state = hass.states.get(f"number.{serial_number}_{entity}_key_{key}")
            assert state is None


@pytest.mark.parametrize(
    "device_fixture",
    [LaMarzoccoModel.GS3_MP],
)
async def test_not_existing_entites(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Assert not existing entities."""

    serial_number = mock_lamarzocco.serial_number

    for entity in (
        "prebrew_off_time",
        "prebrew_on_time",
        "preinfusion_time",
        "set_dose",
    ):
        state = hass.states.get(f"number.{serial_number}_{entity}")
        assert state is None


@pytest.mark.parametrize("device_fixture", [LaMarzoccoModel.LINEA_MICRA])
async def test_not_settable_entites(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
) -> None:
    """Assert not settable causes error."""

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"number.{serial_number}_preinfusion_time")
    assert state
    assert state.state == STATE_UNAVAILABLE
