"""Common fixtures for the Victron VRM Forecasts tests."""

from collections.abc import Generator
import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from victron_vrm.models.aggregations import ForecastAggregations

from homeassistant.components.victron_remote_monitoring.const import (
    CONF_API_TOKEN,
    CONF_SITE_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONST_1_HOUR = 3600000
CONST_12_HOURS = 43200000
CONST_24_HOURS = 86400000
CONST_FORECAST_START = 1745359200000
CONST_FORECAST_END = CONST_FORECAST_START + (CONST_24_HOURS * 2) + (CONST_1_HOUR * 13)
# Do not change the values in this fixture; tests depend on them
CONST_FORECAST_RECORDS = [
    # Yesterday
    [CONST_FORECAST_START + CONST_12_HOURS, 5050.1],
    [CONST_FORECAST_START + (CONST_12_HOURS + CONST_1_HOUR), 5000.2],
    # Today
    [CONST_FORECAST_START + (CONST_24_HOURS + CONST_12_HOURS), 2250.3],
    [CONST_FORECAST_START + CONST_24_HOURS + (CONST_1_HOUR * 13), 2000.4],
    # Tomorrow
    [CONST_FORECAST_START + (CONST_24_HOURS * 2) + CONST_12_HOURS, 1000.5],
    [CONST_FORECAST_START + (CONST_24_HOURS * 2) + (CONST_1_HOUR * 13), 500.6],
]


class FakeDevice:
    """Simple representation of a Victron device."""

    def __init__(
        self,
        *,
        unique_id: str,
        device_id: str,
        name: str,
        manufacturer: str | None = None,
        model: str | None = None,
        serial_number: str | None = None,
    ) -> None:
        """Initialize a fake device."""
        self.unique_id = unique_id
        self.device_id = device_id
        self.name = name
        self.manufacturer = manufacturer
        self.model = model
        self.serial_number = serial_number


class FakeMetric:
    """Simple representation of a Victron metric."""

    def __init__(
        self,
        *,
        metric_kind,
        metric_type,
        metric_nature,
        unit_of_measurement: str | None,
        precision: int | None,
        short_id: str,
        unique_id: str,
        name: str | None,
        value,
    ) -> None:
        """Initialize a fake metric."""
        self.metric_kind = metric_kind
        self.metric_type = metric_type
        self.metric_nature = metric_nature
        self.unit_of_measurement = unit_of_measurement
        self.precision = precision
        self.short_id = short_id
        self.unique_id = unique_id
        self.name = name
        self.value = value
        self.on_update = None


class FakeWritableMetric(FakeMetric):
    """Writable metric used by number/select/switch/button/time entities."""

    def __init__(
        self,
        *,
        enum_values: list[str] | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        step: float | None = None,
        **kwargs,
    ) -> None:
        """Initialize a writable metric with optional constraints."""
        super().__init__(**kwargs)
        self.enum_values = enum_values
        self.min_value = min_value
        self.max_value = max_value
        self.step = step

    def set(self, value) -> None:
        """Store a new value locally for tests."""
        self.value = value


class FakeMQTTClient:
    """Fake MQTT client used for tests."""

    def __init__(self, metrics) -> None:
        """Initialize the fake MQTT client."""
        self.on_new_metric = None
        self._metrics = metrics

    async def connect(self) -> None:
        """Simulate connecting the MQTT client by emitting metrics."""
        if self.on_new_metric is None:
            return
        for device, metric in self._metrics:
            self.on_new_metric(self, device, metric)

    async def disconnect(self) -> None:
        """Simulate disconnecting the MQTT client."""
        return


@pytest.fixture
def mock_setup_entry(mock_vrm_client) -> Generator[AsyncMock]:
    """Override async_setup_entry while client is patched."""
    with patch(
        "homeassistant.components.victron_remote_monitoring.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Override async_config_entry."""
    return MockConfigEntry(
        title="Test VRM Forecasts",
        unique_id="123456",
        version=1,
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: "test_api_key",
            CONF_SITE_ID: 123456,
        },
        options={},
    )


@pytest.fixture
def mqtt_metrics() -> list[tuple[FakeDevice, FakeMetric]]:
    """Return MQTT metrics to emit during connect."""
    return []


@pytest.fixture
def mock_mqtt_client(
    mqtt_metrics: list[tuple[FakeDevice, FakeMetric]],
) -> FakeMQTTClient:
    """Return a fake MQTT client."""
    return FakeMQTTClient(mqtt_metrics)


@pytest.fixture(autouse=True)
def mock_vrm_client(mock_mqtt_client: FakeMQTTClient) -> Generator[AsyncMock]:
    """Patch the VictronVRMClient to supply forecast and site data."""

    def fake_dt_now():
        return datetime.datetime.fromtimestamp(
            (CONST_FORECAST_START + (CONST_24_HOURS + CONST_12_HOURS) + 60000) / 1000,
            tz=datetime.UTC,
        )

    solar_agg = ForecastAggregations(
        start=CONST_FORECAST_START // 1000,
        end=CONST_FORECAST_END // 1000,
        records=[(x // 1000, y) for x, y in CONST_FORECAST_RECORDS],
        custom_dt_now=fake_dt_now,
        site_id=123456,
    )
    consumption_agg = ForecastAggregations(
        start=CONST_FORECAST_START // 1000,
        end=CONST_FORECAST_END // 1000,
        records=[(x // 1000, y) for x, y in CONST_FORECAST_RECORDS],
        custom_dt_now=fake_dt_now,
        site_id=123456,
    )

    site_obj = Mock()
    site_obj.id = 123456
    site_obj.name = "Test Site"

    with (
        patch(
            "homeassistant.components.victron_remote_monitoring.coordinator.VictronVRMClient",
            autospec=True,
        ) as mock_client_cls,
        patch(
            "homeassistant.components.victron_remote_monitoring.config_flow.VictronVRMClient",
            new=mock_client_cls,
        ),
    ):
        client = mock_client_cls.return_value
        # installations.stats returns dict used by get_forecast
        client.installations.stats = AsyncMock(
            return_value={"solar_yield": solar_agg, "consumption": consumption_agg}
        )
        client.get_mqtt_client_for_installation = AsyncMock(
            return_value=mock_mqtt_client
        )
        # users.* used by config flow
        client.users.list_sites = AsyncMock(return_value=[site_obj])
        client.users.get_site = AsyncMock(return_value=site_obj)
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Mock Victron VRM Forecasts for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
