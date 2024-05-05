"""Common fixtures for the Arve tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from asyncarve import ArveCustomer, ArveDevices, ArveSensPro, ArveSensProData
import pytest

from homeassistant.components.arve.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.arve.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, mock_arve: MagicMock) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Arve", domain=DOMAIN, data=USER_INPUT, unique_id=mock_arve.customer_id
    )


@pytest.fixture
def mock_arve():
    """Return a mocked Arve client."""

    with (
        patch(
            "homeassistant.components.arve.coordinator.Arve", autospec=True
        ) as arve_mock,
        patch("homeassistant.components.arve.config_flow.Arve", new=arve_mock),
    ):
        arve = arve_mock.return_value
        arve.customer_id = 12345

        arve.get_customer_id.return_value = ArveCustomer(12345)

        arve.get_devices.return_value = ArveDevices(["test-serial-number"])
        arve.get_sensor_info.return_value = ArveSensPro("Test Sensor", "1.0", "prov1")

        arve.device_sensor_data.return_value = ArveSensProData(
            14, 595.75, 28.71, 0.16, 0.19, 26.02, 7
        )

        yield arve
