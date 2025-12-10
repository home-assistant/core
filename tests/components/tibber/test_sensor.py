"""Tests for Tibber sensor platform."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.tibber.const import (
    DOMAIN,
    PRICE_INTERVAL_15MIN,
    PRICE_INTERVAL_HOURLY,
)
from homeassistant.components.tibber.sensor import (
    RT_SENSORS,
    SENSORS,
    TibberDataSensor,
    TibberSensorElPrice,
    TibberSensorRT,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.fixture
def mock_tibber_home():
    """Create a mock Tibber home."""
    home = AsyncMock()
    home.home_id = "test_home_id"
    home.currency = "NOK"
    home.price_unit = "NOK/kWh"
    home.has_active_subscription = True
    home.has_real_time_consumption = False
    home.rt_subscription_running = False
    home.last_data_timestamp = dt_util.now()
    home.price_total = 1.5
    home.info = {
        "viewer": {
            "home": {
                "appNickname": "Test Home",
                "address": {"address1": "Test Address"},
                "meteringPointData": {
                    "consumptionEan": "test_ean",
                    "gridCompany": "Test Grid",
                    "estimatedAnnualConsumption": 5000,
                },
            }
        }
    }
    home.current_price_data = MagicMock(return_value=(1.5, dt_util.now(), "NORMAL"))
    home.current_attributes = MagicMock(
        return_value={
            "max_price": 2.0,
            "avg_price": 1.5,
            "min_price": 1.0,
        }
    )
    home.price_info_today = [
        {
            "startsAt": dt_util.now().isoformat(),
            "total": 1.5,
            "level": "NORMAL",
        }
    ]
    home.update_info_and_price_info = AsyncMock()
    return home


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "data": {"liveMeasurement": {"power": 1000, "averagePower": 950}}
    }
    coordinator.get_live_measurement.return_value = {"power": 1000, "averagePower": 950}
    return coordinator


class TestTibberSensorSetup:
    """Test Tibber sensor setup."""

    async def test_async_setup_entry_success(
        self, hass: HomeAssistant, mock_tibber_home
    ):
        """Test successful sensor setup."""
        config_entry = MockConfigEntry(
            domain=DOMAIN, data={"access_token": "test_token"}
        )
        config_entry.add_to_hass(hass)

        tibber_connection = MagicMock()
        tibber_connection.get_homes.return_value = [mock_tibber_home]
        hass.data[DOMAIN] = tibber_connection

        async_add_entities = MagicMock()

        with patch("homeassistant.components.tibber.sensor.TibberDataCoordinator"):
            await async_setup_entry(hass, config_entry, async_add_entities)

        assert async_add_entities.called
        entities = async_add_entities.call_args[0][0]
        assert len(entities) > 0
        assert any(isinstance(entity, TibberSensorElPrice) for entity in entities)

    async def test_async_setup_entry_timeout_error(
        self, hass: HomeAssistant, mock_tibber_home
    ):
        """Test sensor setup with timeout error."""
        config_entry = MockConfigEntry(
            domain=DOMAIN, data={"access_token": "test_token"}
        )
        config_entry.add_to_hass(hass)

        mock_tibber_home.update_info.side_effect = TimeoutError("Timeout")
        tibber_connection = MagicMock()
        tibber_connection.get_homes.return_value = [mock_tibber_home]
        hass.data[DOMAIN] = tibber_connection

        async_add_entities = MagicMock()

        with pytest.raises(PlatformNotReady):
            await async_setup_entry(hass, config_entry, async_add_entities)

    async def test_async_setup_entry_with_real_time(
        self, hass: HomeAssistant, mock_tibber_home
    ):
        """Test sensor setup with real-time consumption."""
        config_entry = MockConfigEntry(
            domain=DOMAIN, data={"access_token": "test_token"}
        )
        config_entry.add_to_hass(hass)

        mock_tibber_home.has_real_time_consumption = True
        tibber_connection = MagicMock()
        tibber_connection.get_homes.return_value = [mock_tibber_home]
        hass.data[DOMAIN] = tibber_connection

        async_add_entities = MagicMock()
        await async_setup_entry(hass, config_entry, async_add_entities)

        mock_tibber_home.rt_subscribe.assert_called_once()


class TestTibberSensorElPrice:
    """Test TibberSensorElPrice class."""

    def test_init(self, mock_tibber_home):
        """Test sensor initialization."""
        sensor = TibberSensorElPrice(mock_tibber_home)

        assert sensor._tibber_home == mock_tibber_home
        assert sensor._attr_unique_id == mock_tibber_home.home_id
        assert sensor._attr_translation_key == "electricity_price"
        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT

    def test_device_info(self, mock_tibber_home):
        """Test device info property."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        device_info = sensor.device_info

        assert device_info["identifiers"] == {(DOMAIN, mock_tibber_home.home_id)}
        assert device_info["name"] == "Test Home"
        assert device_info["manufacturer"] == "Tibber"

    def test_update_interval_calculation(self, mock_tibber_home):
        """Test update interval calculation."""
        sensor = TibberSensorElPrice(mock_tibber_home)

        assert sensor._get_update_interval_minutes(PRICE_INTERVAL_HOURLY) == 60
        assert sensor._get_update_interval_minutes(PRICE_INTERVAL_15MIN) == 15
        assert sensor._get_update_interval_minutes("invalid") == 60

    def test_skip_update_logic(self, mock_tibber_home):
        """Test update skip logic."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        now = dt_util.now()

        # Should not skip if no previous update
        assert not sensor._should_skip_update(now, 60)

        # Set up conditions for skip check
        sensor._last_updated = now - dt.timedelta(minutes=30)
        sensor._tibber_home.price_total = 1.5
        sensor._tibber_home.last_data_timestamp = now

        # Should skip if within interval
        assert sensor._should_skip_update(now, 60)
        assert not sensor._should_skip_update(now, 15)

    def test_price_data_retrieval(self, mock_tibber_home):
        """Test price data retrieval."""
        sensor = TibberSensorElPrice(mock_tibber_home)

        # Test hourly data
        hourly_data = sensor._get_hourly_price_data()
        assert len(hourly_data) == 1
        assert hourly_data[0]["total"] == 1.5

        # Test 15-minute data generation
        min_data = sensor._get_15min_price_data()
        assert len(min_data) == 4  # 4 intervals per hour

    async def test_async_update(self, hass: HomeAssistant, mock_tibber_home):
        """Test sensor update."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        sensor.hass = hass

        with patch.object(sensor, "_fetch_data", return_value=True):
            await sensor.async_update()

        assert sensor._attr_native_value == 1.5
        assert sensor._attr_available is True
        assert sensor._attr_native_unit_of_measurement == "NOK/kWh"

    async def test_fetch_data_success(self, mock_tibber_home):
        """Test successful data fetching."""
        sensor = TibberSensorElPrice(mock_tibber_home)

        result = await sensor._fetch_data()

        assert result is True
        mock_tibber_home.update_info_and_price_info.assert_called_once()

    async def test_fetch_data_failure(self, mock_tibber_home):
        """Test failed data fetching."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        mock_tibber_home.update_info_and_price_info.side_effect = Exception("API Error")

        result = await sensor._fetch_data()
        assert result is False


class TestTibberDataSensor:
    """Test TibberDataSensor class."""

    def test_init(self, mock_tibber_home, mock_coordinator):
        """Test sensor initialization."""
        entity_description = SENSORS[0]
        sensor = TibberDataSensor(
            mock_tibber_home, mock_coordinator, entity_description
        )

        assert sensor._tibber_home == mock_tibber_home
        assert sensor.coordinator == mock_coordinator
        assert sensor.entity_description == entity_description

    def test_native_value(self, mock_tibber_home, mock_coordinator):
        """Test native value property."""
        entity_description = SENSORS[0]
        sensor = TibberDataSensor(
            mock_tibber_home, mock_coordinator, entity_description
        )

        setattr(mock_tibber_home, entity_description.key, 123.45)
        assert sensor.native_value == 123.45


class TestTibberSensorRT:
    """Test TibberSensorRT class."""

    def test_init(self, mock_tibber_home, mock_coordinator):
        """Test RT sensor initialization."""
        description = RT_SENSORS[0]
        initial_state = 1000.0

        sensor = TibberSensorRT(
            mock_tibber_home, description, initial_state, mock_coordinator
        )

        assert sensor._tibber_home == mock_tibber_home
        assert sensor.coordinator == mock_coordinator
        assert sensor._attr_native_value == initial_state

    def test_available_property(self, mock_tibber_home, mock_coordinator):
        """Test available property."""
        description = RT_SENSORS[0]
        sensor = TibberSensorRT(mock_tibber_home, description, 1000.0, mock_coordinator)

        mock_tibber_home.rt_subscription_running = True
        assert sensor.available is True

        mock_tibber_home.rt_subscription_running = False
        assert sensor.available is False

    def test_coordinator_update(self, mock_tibber_home, mock_coordinator):
        """Test coordinator update handling."""
        description = RT_SENSORS[1]  # power
        sensor = TibberSensorRT(mock_tibber_home, description, 1000.0, mock_coordinator)

        live_measurement = {"power": 1500.0, "timestamp": dt_util.now().isoformat()}
        mock_coordinator.get_live_measurement.return_value = live_measurement

        with patch.object(sensor, "async_write_ha_state") as mock_write_state:
            sensor._handle_coordinator_update()

        assert sensor._attr_native_value == 1500.0
        mock_write_state.assert_called_once()
