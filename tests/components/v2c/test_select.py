"""Test the V2C select platform."""

from unittest.mock import AsyncMock, patch

import pytest
from pytrydan import DynamicPowerMode
from pytrydan.models.trydan import ChargeMode
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.input_number import (
    ATTR_VALUE,
    DOMAIN as INPUT_NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.v2c.const import (
    CONF_CONTRACTED_POWER_ENTITY,
    CONF_POWER_DEVIATION_ENTITY,
    CONF_PV_AVAILABLE,
    DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform

DYNAMIC_POWER_MODE_ENTITY = "select.evse_1_1_1_1_dynamic_power_mode"
CONTRACTED_POWER_HELPER = "input_number.contracted_power"
POWER_DEVIATION_HELPER = "input_number.power_deviation"


async def _setup_helpers(hass: HomeAssistant) -> None:
    """Set up the external input_number helper entities."""
    assert await async_setup_component(
        hass,
        INPUT_NUMBER_DOMAIN,
        {
            INPUT_NUMBER_DOMAIN: {
                "contracted_power": {
                    "min": 0,
                    "max": 10000,
                    "step": 100,
                    "initial": 4600,
                },
                "power_deviation": {
                    "min": -5000,
                    "max": 5000,
                    "step": 100,
                    "initial": 0,
                },
            }
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
def mock_pv_config_entry() -> MockConfigEntry:
    """Config entry with PV enabled and the helper entities configured."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="da58ee91f38c2406c2a36d0a1a7f8569",
        title="EVSE 1.1.1.1",
        data={CONF_HOST: "1.1.1.1"},
        options={
            CONF_PV_AVAILABLE: True,
            CONF_CONTRACTED_POWER_ENTITY: CONTRACTED_POWER_HELPER,
            CONF_POWER_DEVIATION_ENTITY: POWER_DEVIATION_HELPER,
        },
    )


async def test_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the select entities."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_option(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting an option."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.evse_1_1_1_1_charge_mode",
            ATTR_OPTION: "mixed",
        },
        blocking=True,
    )

    mock_v2c_client.charge_mode.assert_awaited_once_with(ChargeMode.MIXED)


async def test_select_not_created_when_missing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test missing charge mode entity is not created."""
    mock_v2c_client.get_data.return_value.charge_mode = None

    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    entity_id = "select.evse_1_1_1_1_charge_mode"
    assert entity_registry.async_get(entity_id) is None
    assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_created_when_pv_available(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test the dynamic power mode select is created when photovoltaic is enabled."""
    await _setup_helpers(hass)
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    state = hass.states.get(DYNAMIC_POWER_MODE_ENTITY)
    assert state is not None
    assert state.state == str(mock_v2c_client.data.dynamic_power_mode.value)


async def test_dynamic_power_mode_not_created_without_pv(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the dynamic power mode select is absent without photovoltaic."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    assert hass.states.get(DYNAMIC_POWER_MODE_ENTITY) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_not_created_when_data_missing(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test the select is not created when the device has no dynamic power mode."""
    mock_v2c_client.get_data.return_value.dynamic_power_mode = None

    await _setup_helpers(hass)
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    assert hass.states.get(DYNAMIC_POWER_MODE_ENTITY) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_profile(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test selecting the profile mode does not set the contracted power."""

    # The V2C cloud profile is responsible for the contracted power.
    await _setup_helpers(hass)
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: DYNAMIC_POWER_MODE_ENTITY,
            ATTR_OPTION: str(DynamicPowerMode.TIMED_POWER_ENABLED.value),
        },
        blocking=True,
    )

    mock_v2c_client.dynamic_power_mode.assert_awaited_once_with(
        DynamicPowerMode.TIMED_POWER_ENABLED
    )
    mock_v2c_client.contracted_power.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_fv_exclusive(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test FV exclusive mode reads the PV balance helper as contracted power."""
    await _setup_helpers(hass)
    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: POWER_DEVIATION_HELPER, ATTR_VALUE: -500},
        blocking=True,
    )

    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: DYNAMIC_POWER_MODE_ENTITY,
            ATTR_OPTION: str(
                DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED.value
            ),
        },
        blocking=True,
    )

    mock_v2c_client.dynamic_power_mode.assert_awaited_once_with(
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED
    )
    method_names = [method_call[0] for method_call in mock_v2c_client.method_calls]
    mode_call_index = method_names.index("dynamic_power_mode")
    assert method_names[mode_call_index : mode_call_index + 3] == [
        "dynamic_power_mode",
        "get_data",
        "contracted_power",
    ]
    mock_v2c_client.contracted_power.assert_awaited_once_with(-500)


@pytest.mark.parametrize(
    "mode",
    [
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_MIN_MODE_SETTED,
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_GRID_MODE_SETTED,
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_STOP_MODE_SETTED,
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_other_modes(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
    mode: DynamicPowerMode,
) -> None:
    """Test non-FV-exclusive modes read the contracted power helper value."""
    await _setup_helpers(hass)
    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: CONTRACTED_POWER_HELPER, ATTR_VALUE: 6000},
        blocking=True,
    )
    mock_v2c_client.contracted_power.reset_mock()

    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: DYNAMIC_POWER_MODE_ENTITY,
            ATTR_OPTION: str(mode.value),
        },
        blocking=True,
    )

    mock_v2c_client.dynamic_power_mode.assert_awaited_once_with(mode)
    mock_v2c_client.contracted_power.assert_awaited_once_with(6000)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_missing_helper_config(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
) -> None:
    """Test changing mode raises when a helper entity is not configured."""

    # With PV enabled but no helper entities set in the options,
    # _get_contracted_power receives None and raises.
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="da58ee91f38c2406c2a36d0a1a7f8569",
        title="EVSE 1.1.1.1",
        data={CONF_HOST: "1.1.1.1"},
        options={CONF_PV_AVAILABLE: True},
    )

    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: DYNAMIC_POWER_MODE_ENTITY,
                ATTR_OPTION: str(
                    DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_GRID_MODE_SETTED.value
                ),
            },
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_helper_state_unknown(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test changing mode raises when the helper entity has no valid state."""

    # The helper is configured in the options but has never been created, so
    # hass.states.get returns None and _get_contracted_power raises.
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: DYNAMIC_POWER_MODE_ENTITY,
                ATTR_OPTION: str(
                    DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_GRID_MODE_SETTED.value
                ),
            },
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_contracted_power_helper_state_change(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test a contracted power helper change pushes to the API in non-excluded modes."""

    # The device is in FV_MIN mode (from the mock data), so a change to the
    # contracted power helper must be written through to the API.
    mock_v2c_client.data.dynamic_power_mode = (
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_MIN_MODE_SETTED
    )
    await _setup_helpers(hass)
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    mock_v2c_client.contracted_power.reset_mock()

    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: CONTRACTED_POWER_HELPER, ATTR_VALUE: 7000},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_v2c_client.contracted_power.assert_awaited_once_with(7000)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_contracted_power_helper_state_change_excluded_mode(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test a contracted power helper change is ignored in FV exclusive mode."""

    # In FV exclusive (and profile) modes the contracted power helper does not
    # map to the API contracted power, so no write must happen.
    mock_v2c_client.data.dynamic_power_mode = (
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED
    )
    await _setup_helpers(hass)
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    mock_v2c_client.contracted_power.reset_mock()

    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: CONTRACTED_POWER_HELPER, ATTR_VALUE: 7000},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_v2c_client.contracted_power.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_power_deviation_helper_state_change(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test a PV balance helper change pushes to the API in FV exclusive mode."""
    mock_v2c_client.data.dynamic_power_mode = (
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED
    )
    await _setup_helpers(hass)
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    mock_v2c_client.contracted_power.reset_mock()

    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: POWER_DEVIATION_HELPER, ATTR_VALUE: -300},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_v2c_client.contracted_power.assert_awaited_once_with(-300)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_power_deviation_helper_state_change_other_mode(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test a PV balance helper change is ignored outside FV exclusive mode."""
    mock_v2c_client.data.dynamic_power_mode = (
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_MIN_MODE_SETTED
    )
    await _setup_helpers(hass)
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    mock_v2c_client.contracted_power.reset_mock()

    await hass.services.async_call(
        INPUT_NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: POWER_DEVIATION_HELPER, ATTR_VALUE: -300},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_v2c_client.contracted_power.assert_not_called()
