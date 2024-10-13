"""Tests for the La Marzocco number entities."""

from unittest.mock import MagicMock

from lmcloud.const import (
    KEYS_PER_MODEL,
    BoilerType,
    MachineModel,
    PhysicalKey,
    PrebrewMode,
)
from lmcloud.exceptions import RequestNotSuccessful
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry


async def test_coffee_boiler(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco coffee temperature Number."""

    await async_init_integration(hass, mock_config_entry)
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
            ATTR_VALUE: 94,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_temp.mock_calls) == 1
    mock_lamarzocco.set_temp.assert_called_once_with(
        boiler=BoilerType.COFFEE, temperature=94
    )


@pytest.mark.parametrize("device_fixture", [MachineModel.GS3_AV, MachineModel.GS3_MP])
@pytest.mark.parametrize(
    ("entity_name", "value", "func_name", "kwargs"),
    [
        (
            "steam_target_temperature",
            131,
            "set_temp",
            {"boiler": BoilerType.STEAM, "temperature": 131},
        ),
        ("tea_water_duration", 15, "set_dose_tea_water", {"dose": 15}),
    ],
)
async def test_gs3_exclusive(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    entity_name: str,
    value: float,
    func_name: str,
    kwargs: dict[str, float],
) -> None:
    """Test exclusive entities for GS3 AV/MP."""
    await async_init_integration(hass, mock_config_entry)
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
    "device_fixture", [MachineModel.LINEA_MICRA, MachineModel.LINEA_MINI]
)
async def test_gs3_exclusive_none(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure GS3 exclusive is None for unsupported models."""
    await async_init_integration(hass, mock_config_entry)
    ENTITIES = ("steam_target_temperature", "tea_water_duration")

    serial_number = mock_lamarzocco.serial_number
    for entity in ENTITIES:
        state = hass.states.get(f"number.{serial_number}_{entity}")
        assert state is None


@pytest.mark.parametrize(
    "device_fixture", [MachineModel.LINEA_MICRA, MachineModel.LINEA_MINI]
)
@pytest.mark.parametrize(
    ("entity_name", "function_name", "prebrew_mode", "value", "kwargs"),
    [
        (
            "prebrew_off_time",
            "set_prebrew_time",
            PrebrewMode.PREBREW,
            6,
            {"prebrew_off_time": 6.0, "key": PhysicalKey.A},
        ),
        (
            "prebrew_on_time",
            "set_prebrew_time",
            PrebrewMode.PREBREW,
            6,
            {"prebrew_on_time": 6.0, "key": PhysicalKey.A},
        ),
        (
            "preinfusion_time",
            "set_preinfusion_time",
            PrebrewMode.PREINFUSION,
            7,
            {"preinfusion_time": 7.0, "key": PhysicalKey.A},
        ),
    ],
)
async def test_pre_brew_infusion_numbers(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_name: str,
    function_name: str,
    prebrew_mode: PrebrewMode,
    value: float,
    kwargs: dict[str, float],
) -> None:
    """Test the La Marzocco prebrew/-infusion sensors."""

    mock_lamarzocco.config.prebrew_mode = prebrew_mode
    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    state = hass.states.get(f"number.{serial_number}_{entity_name}")

    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

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

    function = getattr(mock_lamarzocco, function_name)
    function.assert_called_once_with(**kwargs)


@pytest.mark.parametrize(
    "device_fixture", [MachineModel.LINEA_MICRA, MachineModel.LINEA_MINI]
)
@pytest.mark.parametrize(
    ("prebrew_mode", "entity", "unavailable"),
    [
        (
            PrebrewMode.PREBREW,
            ("prebrew_off_time", "prebrew_on_time"),
            ("preinfusion_time",),
        ),
        (
            PrebrewMode.PREINFUSION,
            ("preinfusion_time",),
            ("prebrew_off_time", "prebrew_on_time"),
        ),
    ],
)
async def test_pre_brew_infusion_numbers_unavailable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    prebrew_mode: PrebrewMode,
    entity: tuple[str, ...],
    unavailable: tuple[str, ...],
) -> None:
    """Test entities are unavailable depending on selected state."""

    mock_lamarzocco.config.prebrew_mode = prebrew_mode
    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number
    for entity_name in entity:
        state = hass.states.get(f"number.{serial_number}_{entity_name}")
        assert state
        assert state.state != STATE_UNAVAILABLE

    for entity_name in unavailable:
        state = hass.states.get(f"number.{serial_number}_{entity_name}")
        assert state
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_fixture", [MachineModel.GS3_AV])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_name", "value", "prebrew_mode", "function_name", "kwargs"),
    [
        (
            "prebrew_off_time",
            6,
            PrebrewMode.PREBREW,
            "set_prebrew_time",
            {"prebrew_off_time": 6.0},
        ),
        (
            "prebrew_on_time",
            6,
            PrebrewMode.PREBREW,
            "set_prebrew_time",
            {"prebrew_on_time": 6.0},
        ),
        (
            "preinfusion_time",
            7,
            PrebrewMode.PREINFUSION,
            "set_preinfusion_time",
            {"preinfusion_time": 7.0},
        ),
        ("dose", 6, PrebrewMode.DISABLED, "set_dose", {"dose": 6}),
    ],
)
async def test_pre_brew_infusion_key_numbers(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_name: str,
    value: float,
    prebrew_mode: PrebrewMode,
    function_name: str,
    kwargs: dict[str, float],
) -> None:
    """Test the La Marzocco number sensors for GS3AV model."""

    mock_lamarzocco.config.prebrew_mode = prebrew_mode
    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    func = getattr(mock_lamarzocco, function_name)

    state = hass.states.get(f"number.{serial_number}_{entity_name}")
    assert state is None

    for key in PhysicalKey:
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

        assert len(func.mock_calls) == key.value
        func.assert_called_with(**kwargs)


@pytest.mark.parametrize("device_fixture", [MachineModel.GS3_AV])
async def test_disabled_entites(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco prebrew/-infusion sensors for GS3AV model."""
    await async_init_integration(hass, mock_config_entry)
    ENTITIES = (
        "prebrew_off_time",
        "prebrew_on_time",
        "preinfusion_time",
        "set_dose",
    )

    serial_number = mock_lamarzocco.serial_number

    for entity_name in ENTITIES:
        for key in PhysicalKey:
            state = hass.states.get(f"number.{serial_number}_{entity_name}_key_{key}")
            assert state is None


@pytest.mark.parametrize(
    "device_fixture",
    [MachineModel.GS3_MP, MachineModel.LINEA_MICRA, MachineModel.LINEA_MINI],
)
async def test_not_existing_key_entities(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Assert not existing key entities."""
    await async_init_integration(hass, mock_config_entry)
    serial_number = mock_lamarzocco.serial_number

    for entity in (
        "prebrew_off_time",
        "prebrew_on_time",
        "preinfusion_time",
        "set_dose",
    ):
        for key in range(1, KEYS_PER_MODEL[MachineModel.GS3_AV] + 1):
            state = hass.states.get(f"number.{serial_number}_{entity}_key_{key}")
            assert state is None


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

    mock_lamarzocco.set_temp.side_effect = RequestNotSuccessful("Boom")
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

    state = hass.states.get(f"number.{serial_number}_dose_key_1")
    assert state

    mock_lamarzocco.set_dose.side_effect = RequestNotSuccessful("Boom")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: f"number.{serial_number}_dose_key_1",
                ATTR_VALUE: 99,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "number_exception_key"
