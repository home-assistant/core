"""Test Kingspan Watchman SENSiT sensor states."""

from datetime import UTC, timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from connectsensor.exceptions import (
    KingspanAPIError,
    KingspanErrorCode,
    KingspanNoDataError,
    KingspanTimeoutError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

import homeassistant
from homeassistant.components.watchman.const import DEFAULT_OIL_ENERGY_DENSITY, DOMAIN
from homeassistant.components.watchman.coordinator import TankData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util.dt import get_time_zone, set_default_time_zone

from .conftest import MockAsyncTank
from .const import (
    MOCK_CONFIG,
    MOCK_TANK_CAPACITY,
    MOCK_TANK_LEVEL,
    MOCK_TANK_NAME,
    HistoryType,
)


async def test_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_sensor_client
) -> None:
    """Test sensor."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    freezer.tick(timedelta(hours=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tanky_mctankface_oil_level")
    assert state
    assert float(state.state) == float(MOCK_TANK_LEVEL)

    state = hass.states.get("sensor.tanky_mctankface_tank_capacity")
    assert state
    assert float(state.state) == float(MOCK_TANK_CAPACITY)

    state = hass.states.get("sensor.tanky_mctankface_tank_percentage_full")
    assert state
    assert float(state.state) == float(100 * (MOCK_TANK_LEVEL / MOCK_TANK_CAPACITY))

    state = hass.states.get("sensor.tanky_mctankface_current_usage")
    assert state.state == "4.0"

    state = hass.states.get("sensor.tanky_mctankface_forecast_empty")
    assert state.state == "10"

    unload_ok = await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert unload_ok
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("tz", ["America/New_York", "UTC", "Europe/Budapest"])
async def test_sensor_timezones(hass: HomeAssistant, mock_sensor_client, tz) -> None:
    """Test sensor timezone compliance."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)

    set_default_time_zone(get_time_zone(tz))

    reference_date = (
        homeassistant.util.dt.now(ZoneInfo(tz))
        .replace(hour=0, minute=30, second=0, microsecond=0)
        .astimezone(UTC)
        .isoformat()
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tanky_mctankface_last_reading_date")
    assert state
    assert state.state == reference_date

    unload_ok = await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert unload_ok
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_current_energy_usage(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_sensor_client
) -> None:
    """Test current energy usage sensor."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry.async_update_entity(
        "sensor.tanky_mctankface_current_energy_usage",
        disabled_by=None,
    )
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tanky_mctankface_current_energy_usage")
    coordinator = config_entry.runtime_data
    assert state is not None
    assert state.state == str(
        round((coordinator.data[0].usage_rate / 24) * DEFAULT_OIL_ENERGY_DENSITY, 1)
    )

    unload_ok = await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert unload_ok
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_msg", "translation_key"),
    [
        (
            KingspanTimeoutError("connection timeout"),
            "Timed out while connecting to the Kingspan service",
            "timed_out",
        ),
        (
            KingspanAPIError("api-test error", KingspanErrorCode.CANNOT_CONNECT),
            "api-test error",
            None,
        ),
    ],
)
async def test_sensor_exceptions(
    hass: HomeAssistant, mock_sensor_client, side_effect, expected_msg, translation_key
) -> None:
    """Test coordinator handles update exceptions cleanly."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data

    # Contextually inject an exploding mock, completely bypassing conftest
    with patch(
        "homeassistant.components.watchman.coordinator.AsyncSensorClient"
    ) as mock_class:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.login.side_effect = side_effect
        mock_class.return_value = mock_instance

        with pytest.raises(UpdateFailed) as exc:
            await coordinator._async_update_data()

    assert str(exc.value).endswith(expected_msg)
    if translation_key:
        assert exc.value.translation_key == translation_key


@pytest.mark.parametrize(
    "mock_sensor_client",
    [
        {
            "tank_level": MOCK_TANK_CAPACITY,
            "history_type": HistoryType.DECREASING,
            "num_tanks": 2,
        }
    ],
    indirect=True,
)
async def test_sensor_multiple_tanks(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_sensor_client
) -> None:
    """Test sensor."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert device_entries[0].name == MOCK_TANK_NAME + " #1"
    assert device_entries[1].name == MOCK_TANK_NAME + " #2"

    unload_ok = await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert unload_ok
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "mock_sensor_client",
    [
        {"tank_level": MOCK_TANK_CAPACITY, "history_type": HistoryType.NONE},
        {"tank_level": MOCK_TANK_CAPACITY, "history_type": HistoryType.EXPIRED},
    ],
    indirect=["mock_sensor_client"],
)
async def test_sensor_zero_usage_history(
    hass: HomeAssistant, mock_sensor_client
) -> None:
    """Test sensor fallback values when history is missing or expired."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.tanky_mctankface_current_usage")
    assert state
    assert state.state == "0.0"

    state = hass.states.get("sensor.tanky_mctankface_forecast_empty")
    assert state
    assert state.state == "0"

    unload_ok = await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert unload_ok
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_dynamic_device_addition(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_sensor_client
) -> None:
    """Test sensors are dynamically added when a new tank appears in the API."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure only the first tank is loaded
    assert hass.states.get("sensor.tanky_mctankface_oil_level") is not None
    assert hass.states.get("sensor.tanky_mctankface_2_oil_level") is None

    # Mock a second tank appearing in a subsequent coordinator refresh
    coordinator = config_entry.runtime_data
    new_tank_1 = coordinator.data[0]
    new_tank_2 = TankData(
        level=500.0,
        capacity=MOCK_TANK_CAPACITY,
        serial_number="20009999",
        name="Tanky McTankFace 2",
    )

    with patch.object(
        coordinator,
        "_async_update_data",
        new_callable=AsyncMock,
        return_value=[new_tank_1, new_tank_2],
    ):
        freezer.tick(timedelta(hours=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Verify the new tank entities were dynamically added without a restart
        assert hass.states.get("sensor.tanky_mctankface_2_oil_level") is not None


@pytest.mark.parametrize(
    "mock_sensor_client",
    [
        {
            "tank_level": MOCK_TANK_CAPACITY,
            "history_type": HistoryType.DECREASING,
            "num_tanks": 2,
        }
    ],
    indirect=True,
)
async def test_skip_tank_with_missing_readings(
    hass: HomeAssistant, mock_sensor_client, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a tank raising NO_DATA is skipped without dropping the whole account."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)

    # Grab the original mocked method so we can allow the second tank to succeed
    original_history = MockAsyncTank.history

    async def mock_history(self):
        if self._tank_num == 1:
            raise KingspanNoDataError("no history data for tank 1")
        return await original_history(self)

    with patch(
        "tests.components.watchman.conftest.MockAsyncTank.history", new=mock_history
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # The first tank should be skipped, so its sensors won't exist
    assert hass.states.get("sensor.tanky_mctankface_1_oil_level") is None
    assert "Skipping tank 'Tanky McTankFace #1' (missing data)" in caplog.text

    # The second tank should successfully load
    assert hass.states.get("sensor.tanky_mctankface_2_oil_level") is not None
    assert float(hass.states.get("sensor.tanky_mctankface_2_oil_level").state) == float(
        MOCK_TANK_CAPACITY
    )


@pytest.mark.parametrize(
    "mock_sensor_client",
    [{"tank_level": MOCK_TANK_CAPACITY, "history_type": HistoryType.DECREASING}],
    indirect=True,
)
async def test_inner_loop_critical_error_re_raises(
    hass: HomeAssistant, mock_sensor_client
) -> None:
    """Test that a non-NO_DATA error on a single tank aborts the coordinator update."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data

    async def mock_history(self):
        raise KingspanTimeoutError("Connection dropped while fetching tank history")

    with (
        patch(
            "tests.components.watchman.conftest.MockAsyncTank.history", new=mock_history
        ),
        pytest.raises(UpdateFailed) as exc,
    ):
        await coordinator._async_update_data()

    assert exc.value.translation_key == "timed_out"
