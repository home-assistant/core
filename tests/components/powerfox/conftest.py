"""Common fixtures for the Powerfox tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from powerfox import (
    Device,
    DeviceReport,
    DeviceType,
    GasReport,
    HeatMeter,
    PowerMeter,
    WaterMeter,
)
import pytest

from homeassistant.components.powerfox.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry


def _power_meter() -> PowerMeter:
    """Return a mocked power meter reading."""
    return PowerMeter(
        outdated=False,
        timestamp=datetime(2024, 11, 26, 10, 48, 51, tzinfo=UTC),
        power=111,
        energy_usage=1111.111,
        energy_return=111.111,
        energy_usage_high_tariff=111.111,
        energy_usage_low_tariff=111.111,
    )


def _water_meter() -> WaterMeter:
    """Return a mocked water meter reading."""
    return WaterMeter(
        outdated=False,
        timestamp=datetime(2024, 11, 26, 10, 48, 51, tzinfo=UTC),
        cold_water=1111.111,
        warm_water=0.0,
    )


def _heat_meter() -> HeatMeter:
    """Return a mocked heat meter reading."""
    return HeatMeter(
        outdated=False,
        timestamp=datetime(2024, 11, 26, 10, 48, 51, tzinfo=UTC),
        total_energy=1111.111,
        delta_energy=111,
        total_volume=1111.111,
        delta_volume=0.111,
    )


def _gas_report() -> DeviceReport:
    """Return a mocked gas report."""
    return DeviceReport(
        gas=GasReport(
            total_delta=100,
            sum=10.5,
            total_delta_currency=5.0,
            current_consumption=0.4,
            current_consumption_kwh=4.0,
            consumption=10.5,
            consumption_kwh=10.5,
            max_consumption=1.5,
            min_consumption=0.2,
            avg_consumption=0.6,
            max_consumption_kwh=1.7,
            min_consumption_kwh=0.1,
            avg_consumption_kwh=0.5,
            sum_currency=2.5,
            max_currency=0.3,
        )
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.powerfox.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_powerfox_client() -> Generator[AsyncMock]:
    """Mock a Powerfox client."""
    with (
        patch(
            "homeassistant.components.powerfox.Powerfox",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.powerfox.config_flow.Powerfox",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.all_devices.return_value = [
            Device(
                id="9x9x1f12xx3x",
                date_added=datetime(2024, 11, 26, 9, 22, 35, tzinfo=UTC),
                main_device=True,
                bidirectional=True,
                type=DeviceType.POWER_METER,
                name="Poweropti",
            ),
            Device(
                id="9x9x1f12xx4x",
                date_added=datetime(2024, 11, 26, 9, 22, 35, tzinfo=UTC),
                main_device=False,
                bidirectional=False,
                type=DeviceType.COLD_WATER_METER,
                name="Wateropti",
            ),
            Device(
                id="9x9x1f12xx5x",
                date_added=datetime(2024, 11, 26, 9, 22, 35, tzinfo=UTC),
                main_device=False,
                bidirectional=False,
                type=DeviceType.HEAT_METER,
                name="Heatopti",
            ),
            Device(
                id="9x9x1f12xx6x",
                date_added=datetime(2024, 11, 26, 9, 22, 35, tzinfo=UTC),
                main_device=False,
                bidirectional=False,
                type=DeviceType.GAS_METER,
                name="Gasopti",
            ),
        ]
        device_factories = {
            "9x9x1f12xx3x": _power_meter,
            "9x9x1f12xx4x": _water_meter,
            "9x9x1f12xx5x": _heat_meter,
        }

        client.device = AsyncMock(
            side_effect=lambda *, device_id: device_factories[device_id]()  # type: ignore[index]
        )
        client.report = AsyncMock(return_value=_gas_report())
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a Powerfox config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Powerfox",
        data={
            CONF_EMAIL: "test@powerfox.test",
            CONF_PASSWORD: "test-password",
        },
    )
