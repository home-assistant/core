"""Common utilities for Vallox tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture
from vallox_websocket_api import MetricData, MetricValue

from homeassistant.components.vallox.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

from . import TEST_HOST, TEST_NAME


@pytest.fixture
def mock_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fetch_metric_data_mock: AsyncMock,
) -> MockConfigEntry:
    """Add the mocked Vallox config entry to Home Assistant."""
    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TEST_NAME,
        data={CONF_HOST: TEST_HOST, CONF_NAME: TEST_NAME},
    )


@pytest.fixture
def default_metrics() -> dict[str, MetricValue]:
    """Return default Vallox metrics."""
    return load_json_object_fixture("metrics.json", DOMAIN)


@pytest.fixture
def mock_vallox_client(
    default_metrics: dict[str, MetricValue],
) -> Generator[AsyncMock]:
    """Return a mocked Vallox client used by both the integration and config flow."""
    with (
        patch("homeassistant.components.vallox.Vallox", autospec=True) as mock_class,
        patch("homeassistant.components.vallox.config_flow.Vallox", new=mock_class),
    ):
        client = mock_class.return_value
        client.fetch_metric_data.return_value = MetricData(default_metrics)
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.vallox.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
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
