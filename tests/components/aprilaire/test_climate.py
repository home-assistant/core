"""Tests for the Aprilaire climate platform."""

from unittest.mock import MagicMock

from pyaprilaire.const import Attribute
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_ON,
    PRESET_AWAY,
    PRESET_NONE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_MAC, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.CLIMATE]


pytestmark = [
    pytest.mark.usefixtures("mock_aprilaire"),
]


def _get_entity_id(entity_registry: er.EntityRegistry, unique_id_suffix: str) -> str:
    """Get entity_id from the entity registry by unique_id suffix."""
    entry = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN, "aprilaire", f"{MOCK_MAC}_{unique_id_suffix}"
    )
    assert entry is not None
    return entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all climate entities via snapshot."""
    entry = await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_climate_set_temperature_auto(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setting temperature in auto mode with high/low."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "thermostat")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_HIGH: 26.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
        },
        blocking=True,
    )

    mock_client.update_setpoint.assert_awaited_once_with(26.0, 19.0)
    mock_client.read_control.assert_awaited()


async def test_climate_set_temperature_single_cool(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test setting single temperature in cool mode."""
    base_coordinator_data[Attribute.MODE] = 3
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "thermostat")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TEMPERATURE: 24.0,
        },
        blocking=True,
    )

    mock_client.update_setpoint.assert_awaited_once_with(24.0, 0)


async def test_climate_set_temperature_single_heat(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test setting single temperature in heat mode."""
    base_coordinator_data[Attribute.MODE] = 2
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "thermostat")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TEMPERATURE: 21.0,
        },
        blocking=True,
    )

    mock_client.update_setpoint.assert_awaited_once_with(0, 21.0)


async def test_climate_set_humidity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setting humidity."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "thermostat")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_humidity",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_HUMIDITY: 40,
        },
        blocking=True,
    )

    mock_client.set_humidification_setpoint.assert_awaited_once_with(40)


async def test_climate_set_fan_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setting fan mode."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "thermostat")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_fan_mode",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_FAN_MODE: FAN_ON,
        },
        blocking=True,
    )

    mock_client.update_fan_mode.assert_awaited_once_with(1)
    mock_client.read_control.assert_awaited()


async def test_climate_set_fan_mode_circulate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setting fan mode to circulate."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "thermostat")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_fan_mode",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_FAN_MODE: "Circulate",
        },
        blocking=True,
    )

    mock_client.update_fan_mode.assert_awaited_once_with(3)


async def test_climate_set_hvac_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setting HVAC mode."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "thermostat")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    mock_client.update_mode.assert_awaited_once_with(2)
    mock_client.read_control.assert_awaited()


async def test_climate_set_preset_away(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setting preset mode to away."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "thermostat")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_preset_mode",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_PRESET_MODE: PRESET_AWAY,
        },
        blocking=True,
    )

    mock_client.set_hold.assert_awaited_once_with(3)
    mock_client.read_scheduling.assert_awaited()


async def test_climate_set_preset_none(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setting preset mode to none."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "thermostat")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_preset_mode",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_PRESET_MODE: PRESET_NONE,
        },
        blocking=True,
    )

    mock_client.set_hold.assert_awaited_once_with(0)
    mock_client.read_scheduling.assert_awaited()
