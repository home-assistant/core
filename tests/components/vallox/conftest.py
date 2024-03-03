"""Common utilities for Vallox tests."""

from unittest.mock import AsyncMock, patch

import pytest
from vallox_websocket_api import MetricData

from homeassistant.components.vallox.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create mocked Vallox config entry."""
    vallox_mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.100.50",
            CONF_NAME: "Vallox",
        },
    )
    vallox_mock_entry.add_to_hass(hass)

    return vallox_mock_entry


@pytest.fixture
def default_metrics():
    """Return default Vallox metrics."""
    return {
        "A_CYC_MACHINE_MODEL": 3,
        "A_CYC_APPL_SW_VERSION_1": 2,
        "A_CYC_APPL_SW_VERSION_2": 0,
        "A_CYC_APPL_SW_VERSION_3": 16,
        "A_CYC_UUID0": 5,
        "A_CYC_UUID1": 6,
        "A_CYC_UUID2": 7,
        "A_CYC_UUID3": 8,
        "A_CYC_UUID4": 9,
        "A_CYC_UUID5": 10,
        "A_CYC_UUID6": 11,
        "A_CYC_UUID7": 12,
        "A_CYC_BOOST_TIMER": 30,
        "A_CYC_FIREPLACE_TIMER": 30,
        "A_CYC_EXTRA_TIMER": 30,
        "A_CYC_MODE": 0,
        "A_CYC_STATE": 0,
        "A_CYC_FILTER_CHANGED_YEAR": 24,
        "A_CYC_FILTER_CHANGED_MONTH": 2,
        "A_CYC_FILTER_CHANGED_DAY": 16,
        "A_CYC_FILTER_CHANGE_INTERVAL": 120,
        "A_CYC_TOTAL_FAULT_COUNT": 0,
        "A_CYC_FAULT_CODE": 0,
        "A_CYC_FAULT_ACTIVITY": 0,
        "A_CYC_FAULT_FIRST_DATE": 0,
        "A_CYC_FAULT_LAST_DATE": 0,
        "A_CYC_FAULT_SEVERITY": 0,
        "A_CYC_FAULT_COUNT": 0,
        "A_CYC_HOME_SPEED_SETTING": 30,
        "A_CYC_AWAY_SPEED_SETTING": 10,
        "A_CYC_BOOST_SPEED_SETTING": 80,
    }


@pytest.fixture(autouse=True)
def fetch_metric_data_mock(default_metrics):
    """Stub the Vallox fetch_metric_data method."""
    with patch(
        "homeassistant.components.vallox.Vallox.fetch_metric_data",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = MetricData(default_metrics)
        yield mock


@pytest.fixture
def setup_fetch_metric_data_mock(fetch_metric_data_mock, default_metrics):
    """Patch the Vallox metrics response."""

    def _setup(metrics=None, metric_data_class=MetricData):
        metrics = metrics or {}
        fetch_metric_data_mock.return_value = metric_data_class(
            {**default_metrics, **metrics}
        )

        return fetch_metric_data_mock

    return _setup


def patch_set_profile():
    """Patch the Vallox metrics set values."""
    return patch("homeassistant.components.vallox.Vallox.set_profile")


def patch_set_fan_speed():
    """Patch the Vallox metrics set values."""
    return patch("homeassistant.components.vallox.Vallox.set_fan_speed")


def patch_set_values():
    """Patch the Vallox metrics set values."""
    return patch("homeassistant.components.vallox.Vallox.set_values")


def patch_set_filter_change_date():
    """Patch the Vallox metrics set filter change date."""
    return patch("homeassistant.components.vallox.Vallox.set_filter_change_date")
