"""Tests for the Hot Spring number platform."""

from unittest.mock import MagicMock, patch

from hotspring import HotSpringConnectionError, HotSpringError, Spa, TemperatureUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hotspring.const import SCAN_INTERVAL
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.util import dt as dt_util

from . import setup_with_selected_platforms

ENTITY_ID = "number.connectedspa_ddeeff_target_temperature"
SALT_OUTPUT_LEVEL_ENTITY_ID = "number.connectedspa_ddeeff_salt_output_level"
SALT_OUTPUT_LEVEL_UNIQUE_ID = "AA:BB:CC:DD:EE:FF_salt_output_level"


@pytest.mark.usefixtures("mock_hotspring")
async def test_number_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the number entity state."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_hotspring")
@pytest.mark.parametrize("cartridge_installed", [True, False])
async def test_initial_numbers_added_together(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    cartridge_installed: bool,
) -> None:
    """Test setup batches all initially supported numbers in one addition."""
    device_fixture.water_care.cartridge_installed = cartridge_installed
    with patch.object(
        EntityPlatform,
        "async_add_entities",
        autospec=True,
        side_effect=EntityPlatform.async_add_entities,
    ) as add_entities:
        await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    add_entities.assert_called_once()
    assert len(add_entities.call_args.args[1]) == 1 + cartridge_installed
    assert hass.states.get(ENTITY_ID) is not None
    assert (
        hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID) is not None
    ) is cartridge_installed


async def test_set_target_temperature(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test setting target temperature."""
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "40.0"

    def set_temp_mock(value: float) -> None:
        device_fixture.heater.set_temperature = value

    mock_hotspring.set_temperature.side_effect = set_temp_mock

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 38,
        },
        blocking=True,
    )

    mock_hotspring.set_temperature.assert_called_once_with(100.0)
    mock_hotspring.update.assert_called_once()
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "37.8"


@pytest.mark.parametrize(
    ("exception", "match"),
    [
        (
            HotSpringConnectionError,
            "An error occurred while communicating with the Hot Spring API",
        ),
        (HotSpringError, "Invalid response received from the Hot Spring API"),
    ],
)
async def test_set_target_temperature_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    exception: type[Exception],
    match: str,
) -> None:
    """Test exception handling when setting target temperature."""
    mock_hotspring.set_temperature.side_effect = exception

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_VALUE: 38,
            },
            blocking=True,
        )


async def test_set_target_temperature_celsius(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting target temperature when the spa is configured in Celsius."""
    device_fixture.heater.temperature_unit = TemperatureUnit.CELSIUS
    device_fixture.heater.set_temperature = 38.5

    def set_temp_mock(value: float) -> None:
        device_fixture.heater.set_temperature = value

    mock_hotspring.set_temperature.side_effect = set_temp_mock

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    assert hass.states.get(ENTITY_ID) == snapshot

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 37.5,
        },
        blocking=True,
    )

    mock_hotspring.set_temperature.assert_called_once_with(37.5)
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "37.5"


@pytest.mark.parametrize(
    ("value", "expected_level"),
    [
        pytest.param(0.0, 0, id="min"),
        pytest.param(7.0, 7, id="mid"),
        pytest.param(10.0, 10, id="max"),
    ],
)
async def test_set_salt_output_level(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
    value: float,
    expected_level: int,
) -> None:
    """Test integral values reach the library as integers."""
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"

    def set_level_mock(level: int) -> None:
        device_fixture.water_care.level = level

    mock_hotspring.set_water_care_level.side_effect = set_level_mock

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: SALT_OUTPUT_LEVEL_ENTITY_ID,
            ATTR_VALUE: value,
        },
        blocking=True,
    )

    mock_hotspring.set_water_care_level.assert_called_once_with(expected_level)
    assert type(mock_hotspring.set_water_care_level.call_args.args[0]) is int
    mock_hotspring.update.assert_called_once()
    mock_hotspring.set_salt_system_power.assert_not_called()
    mock_hotspring.set_water_care_boost.assert_not_called()
    mock_hotspring.toggle_water_care_boost.assert_not_called()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == str(expected_level)


async def test_set_salt_output_level_out_of_range(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test out of range values are rejected by the number platform."""
    with pytest.raises(ServiceValidationError, match="outside valid range"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: SALT_OUTPUT_LEVEL_ENTITY_ID,
                ATTR_VALUE: 11.0,
            },
            blocking=True,
        )

    mock_hotspring.set_water_care_level.assert_not_called()


@pytest.mark.parametrize(
    ("exception", "match"),
    [
        (
            HotSpringConnectionError,
            "An error occurred while communicating with the Hot Spring API",
        ),
        (HotSpringError, "Invalid response received from the Hot Spring API"),
    ],
)
async def test_set_salt_output_level_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    exception: type[Exception],
    match: str,
) -> None:
    """Test exception handling when setting the salt output level."""
    mock_hotspring.set_water_care_level.side_effect = exception

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: SALT_OUTPUT_LEVEL_ENTITY_ID,
                ATTR_VALUE: 3.0,
            },
            blocking=True,
        )

    mock_hotspring.update.assert_called_once()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"


async def test_set_salt_output_level_poll_fails(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test a successful command does not refresh until the next scheduled poll."""
    mock_hotspring.update.reset_mock()
    mock_hotspring.update.side_effect = HotSpringConnectionError

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: SALT_OUTPUT_LEVEL_ENTITY_ID,
            ATTR_VALUE: 5.0,
        },
        blocking=True,
    )

    mock_hotspring.set_water_care_level.assert_called_once_with(5)
    mock_hotspring.update.assert_not_called()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    mock_hotspring.update.side_effect = None
    async_fire_time_changed(hass, dt_util.utcnow() + 2 * SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"


async def test_salt_output_level_unavailable_when_spa_disconnected(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_fixture: Spa,
) -> None:
    """Test the salt output level is unavailable while the spa is disconnected."""
    device_fixture.connection_status.spa_connected = False
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    device_fixture.connection_status.spa_connected = True
    async_fire_time_changed(hass, dt_util.utcnow() + 2 * SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"


async def test_salt_output_level_unavailable_when_cartridge_removed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_fixture: Spa,
) -> None:
    """Test the salt output level is retained but unavailable without a cartridge."""
    device_fixture.water_care.cartridge_installed = False
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    device_fixture.water_care.cartridge_installed = True
    async_fire_time_changed(hass, dt_util.utcnow() + 2 * SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"


@pytest.mark.usefixtures("mock_hotspring")
async def test_no_salt_output_level_entity_without_cartridge(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
) -> None:
    """Test no salt output level entity is created without a cartridge."""
    device_fixture.water_care.cartridge_installed = False
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    assert hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID) is None
    assert hass.states.get(ENTITY_ID) is not None


@pytest.mark.usefixtures("mock_hotspring")
async def test_salt_output_level_entity_added_when_cartridge_reported_later(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the salt output level entity is added once a cartridge is reported."""
    device_fixture.water_care.cartridge_installed = False
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])
    assert hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID) is None

    device_fixture.water_care.cartridge_installed = True
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"

    async_fire_time_changed(hass, dt_util.utcnow() + 2 * SCAN_INTERVAL)
    await hass.async_block_till_done()
    entries = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == SALT_OUTPUT_LEVEL_UNIQUE_ID
    ]
    assert len(entries) == 1


async def test_salt_output_level_entity_not_duplicated_on_reload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a reload does not duplicate the salt output level entity."""
    assert await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    entries = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, init_integration.entry_id
        )
        if entry.unique_id == SALT_OUTPUT_LEVEL_UNIQUE_ID
    ]
    assert len(entries) == 1
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"


async def test_set_salt_output_level_ignores_system_enabled(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test the salt output level stays available when the salt system is disabled."""
    device_fixture.water_care.system_enabled = False
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"

    def set_level_mock(level: int) -> None:
        device_fixture.water_care.level = level

    mock_hotspring.set_water_care_level.side_effect = set_level_mock

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: SALT_OUTPUT_LEVEL_ENTITY_ID,
            ATTR_VALUE: 4.0,
        },
        blocking=True,
    )

    mock_hotspring.set_water_care_level.assert_called_once_with(4)
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "4"


async def test_set_salt_output_level_non_echo_reports_different_level(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test the requested level is not used as confirmed value when the spa does not echo."""
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"

    mock_hotspring.update.reset_mock()

    def update_with_reported_level() -> Spa:
        # The command does not echo; the spa only reports level 5 on the next fetch.
        device_fixture.water_care.level = 5
        return device_fixture

    mock_hotspring.update.side_effect = update_with_reported_level

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: SALT_OUTPUT_LEVEL_ENTITY_ID,
            ATTR_VALUE: 7.0,
        },
        blocking=True,
    )

    mock_hotspring.set_water_care_level.assert_called_once_with(7)
    mock_hotspring.update.assert_not_called()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()
    mock_hotspring.update.assert_called_once()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "5"


async def test_salt_output_level_reflects_external_reduction_via_polling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test polling reflects an external or automatic level reduction without a write."""
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"

    device_fixture.water_care.level = 1
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    mock_hotspring.set_water_care_level.assert_not_called()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "1"
