"""Test the GoodWe number platform."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

from goodwe import InverterError, SensorKind
from goodwe.sensor import Current
import pytest

from homeassistant.components.goodwe.const import (
    CONF_MODEL_FAMILY,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_STEP,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
    NumberDeviceClass,
    NumberMode,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    CONF_PORT,
    EntityCategory,
    UnitOfElectricCurrent,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_HOST, TEST_PORT, TEST_SERIAL

from tests.common import MockConfigEntry

BATTERY_CHARGE_CURRENT = "battery_charge_current"
BATTERY_CHARGE_CURRENT_ENTITY_ID = "number.goodwe_battery_charge_current_limit"
GRID_EXPORT_LIMIT_ENTITY_ID = "number.goodwe_grid_export_limit"

# Setting definition as advertised by the goodwe library for ET inverters
BATTERY_CHARGE_CURRENT_SETTING = Current(
    BATTERY_CHARGE_CURRENT, 45353, "Battery Charge Current", SensorKind.BAT
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked GoodWe config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        version=2,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_MODEL_FAMILY: "ET",
        },
        unique_id=TEST_SERIAL,
    )


def configure_settings(
    mock_inverter: MagicMock, settings: dict[str, Any], advertised: bool = True
) -> None:
    """Configure the settings advertised and readable on the mocked inverter."""
    mock_inverter.settings.return_value = (
        (BATTERY_CHARGE_CURRENT_SETTING,)
        if advertised and BATTERY_CHARGE_CURRENT in settings
        else ()
    )

    async def read_setting(setting_id: str) -> Any:
        if setting_id not in settings:
            raise ValueError(f'Unknown setting "{setting_id}"')
        if isinstance(settings[setting_id], Exception):
            raise settings[setting_id]
        return settings[setting_id]

    mock_inverter.read_setting = AsyncMock(side_effect=read_setting)
    mock_inverter.write_setting = AsyncMock()


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the GoodWe integration."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_battery_charge_current_limit(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the battery charge current limit entity is created from the setting."""
    configure_settings(mock_inverter, {BATTERY_CHARGE_CURRENT: 25.5})
    await setup_integration(hass, mock_config_entry)

    mock_inverter.read_setting.assert_any_call(BATTERY_CHARGE_CURRENT)

    state = hass.states.get(BATTERY_CHARGE_CURRENT_ENTITY_ID)
    assert state is not None
    assert state.state == "25.5"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfElectricCurrent.AMPERE
    assert state.attributes[ATTR_DEVICE_CLASS] == NumberDeviceClass.CURRENT
    assert state.attributes[ATTR_MIN] == 0
    assert state.attributes[ATTR_MAX] == 100
    assert state.attributes[ATTR_STEP] == 0.1
    assert state.attributes[ATTR_MODE] == NumberMode.BOX

    entry = entity_registry.async_get(BATTERY_CHARGE_CURRENT_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{DOMAIN}-{BATTERY_CHARGE_CURRENT}-{TEST_SERIAL}"
    assert entry.entity_category is EntityCategory.CONFIG
    assert entry.translation_key == BATTERY_CHARGE_CURRENT


async def test_battery_charge_current_limit_not_advertised(
    hass: HomeAssistant,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no entity is created and no read is attempted without the setting."""
    configure_settings(mock_inverter, {BATTERY_CHARGE_CURRENT: 25.5}, advertised=False)
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(BATTERY_CHARGE_CURRENT_ENTITY_ID) is None
    assert call(BATTERY_CHARGE_CURRENT) not in mock_inverter.read_setting.call_args_list
    # Other number entities are not affected
    assert hass.states.get(GRID_EXPORT_LIMIT_ENTITY_ID) is not None


@pytest.mark.parametrize(
    "read_result",
    [InverterError("Failed to read setting"), ValueError("Unknown setting"), None],
    ids=["inverter_error", "value_error", "rejected"],
)
async def test_battery_charge_current_limit_read_error(
    hass: HomeAssistant,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
    read_result: Exception | None,
) -> None:
    """Test the entity is omitted when the advertised setting cannot be read."""
    configure_settings(mock_inverter, {BATTERY_CHARGE_CURRENT: read_result})
    await setup_integration(hass, mock_config_entry)

    mock_inverter.read_setting.assert_any_call(BATTERY_CHARGE_CURRENT)
    assert hass.states.get(BATTERY_CHARGE_CURRENT_ENTITY_ID) is None
    # Other number entities are not affected
    assert hass.states.get(GRID_EXPORT_LIMIT_ENTITY_ID) is not None


@pytest.mark.parametrize(
    ("requested_value", "written_value", "expected_state"),
    [
        # Decimal values are written with their 0.1 A resolution
        (20.3, 20.3, "20.3"),
        (7, 7.0, "7.0"),
        (0, 0.0, "0.0"),
        (100, 100.0, "100.0"),
        # Values are rounded to the 0.1 A resolution of the setting
        (20.34, 20.3, "20.3"),
    ],
)
async def test_set_battery_charge_current_limit(
    hass: HomeAssistant,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
    requested_value: float,
    written_value: float,
    expected_state: str,
) -> None:
    """Test setting the battery charge current limit writes the setting."""
    configure_settings(mock_inverter, {BATTERY_CHARGE_CURRENT: 25.5})
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: BATTERY_CHARGE_CURRENT_ENTITY_ID,
            ATTR_VALUE: requested_value,
        },
        blocking=True,
    )

    mock_inverter.write_setting.assert_called_once_with(
        BATTERY_CHARGE_CURRENT, written_value
    )
    assert hass.states.get(BATTERY_CHARGE_CURRENT_ENTITY_ID).state == expected_state


@pytest.mark.parametrize("requested_value", [-0.1, 100.1])
async def test_set_battery_charge_current_limit_out_of_range(
    hass: HomeAssistant,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
    requested_value: float,
) -> None:
    """Test out of range values are rejected without writing to the inverter."""
    configure_settings(mock_inverter, {BATTERY_CHARGE_CURRENT: 25.5})
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: BATTERY_CHARGE_CURRENT_ENTITY_ID,
                ATTR_VALUE: requested_value,
            },
            blocking=True,
        )

    mock_inverter.write_setting.assert_not_called()
    assert hass.states.get(BATTERY_CHARGE_CURRENT_ENTITY_ID).state == "25.5"


async def test_set_battery_charge_current_limit_write_error(
    hass: HomeAssistant,
    mock_inverter: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the state is not updated when writing the setting fails."""
    configure_settings(mock_inverter, {BATTERY_CHARGE_CURRENT: 25.5})
    await setup_integration(hass, mock_config_entry)
    mock_inverter.write_setting.side_effect = InverterError("Failed to write setting")

    with pytest.raises(InverterError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: BATTERY_CHARGE_CURRENT_ENTITY_ID,
                ATTR_VALUE: 20.3,
            },
            blocking=True,
        )

    mock_inverter.write_setting.assert_called_once_with(BATTERY_CHARGE_CURRENT, 20.3)
    assert hass.states.get(BATTERY_CHARGE_CURRENT_ENTITY_ID).state == "25.5"
