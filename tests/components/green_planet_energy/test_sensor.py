"""Test the Green Planet Energy sensor."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors."""
    freezer.move_to("2024-01-01 13:00:00")
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_sensor_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test sensor device info."""
    entry = entity_registry.async_get("sensor.green_planet_energy_highest_price_today")

    assert entry is not None
    assert entry.device_id is not None

    device = device_registry.async_get(entry.device_id)

    assert device is not None
    assert device.name == "Green Planet Energy"
    assert device.entry_type is dr.DeviceEntryType.SERVICE


async def test_lowest_price_day_uses_tomorrow_after_18(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After 18:00 the lowest day-price sensors must switch to tomorrow's data."""
    # 2024-01-02 02:00:00 UTC = 2024-01-01 18:00:00 PST (UTC-8)
    # so dt_util.now().hour == 18, triggering the tomorrow-switch.
    freezer.move_to("2024-01-02 02:00:00+00:00")

    # Return tomorrow's cheapest day slot when current_hour >= 18
    def lowest_price_day_side_effect(
        data: dict, current_hour: int | None = None
    ) -> float:
        if current_hour is not None and current_hour >= 18:
            return 31.0  # 31 Cent/kWh — tomorrow's cheapest at hour 10
        return 26.0

    def lowest_price_day_with_hour_side_effect(
        data: dict, current_hour: int | None = None
    ) -> tuple[float, int]:
        if current_hour is not None and current_hour >= 18:
            return (31.0, 10)
        return (26.0, 6)

    mock_api.get_lowest_price_day.side_effect = lowest_price_day_side_effect
    mock_api.get_lowest_price_day_with_hour.side_effect = (
        lowest_price_day_with_hour_side_effect
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Price sensor must reflect tomorrow's lowest day price
    price_state = hass.states.get(
        "sensor.green_planet_energy_lowest_price_day_06_00_18_00"
    )
    assert price_state is not None
    assert abs(float(price_state.state) - 0.31) < 1e-4

    # Time sensor must point to tomorrow's date at hour 10
    time_state = hass.states.get(
        "sensor.green_planet_energy_lowest_price_day_time_06_00_18_00"
    )
    assert time_state is not None
    state_dt = dt_util.parse_datetime(time_state.state)
    assert state_dt is not None
    local_dt = state_dt.astimezone(dt_util.DEFAULT_TIME_ZONE)
    tomorrow_local = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1))
    assert local_dt.date() == tomorrow_local.date()
    assert local_dt.hour == 10


async def test_lowest_price_night_time_uses_upcoming_night_after_06(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After 06:00 the lowest night-price time sensor must switch to tonight."""
    freezer.move_to("2024-01-01 06:00:00")

    mock_api.get_lowest_price_night_with_hour.return_value = (29.0, 22)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    time_state = hass.states.get(
        "sensor.green_planet_energy_lowest_price_night_time_18_00_06_00"
    )
    assert time_state is not None
    state_dt = dt_util.parse_datetime(time_state.state)
    assert state_dt is not None
    local_dt = state_dt.astimezone(dt_util.DEFAULT_TIME_ZONE)
    assert local_dt.date() == dt_util.now().date()
    assert local_dt.hour == 22
