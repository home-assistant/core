"""Common fixtures for the STIEBEL ELTRON tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pystiebeleltron import ControllerModel
from pystiebeleltron.lwz import OperatingMode
import pytest

from homeassistant.components.stiebel_eltron.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_get_controller_model() -> Generator[MagicMock]:
    """Mock the Stiebel Eltron get_controller_model function."""
    with (
        patch(
            "homeassistant.components.stiebel_eltron.get_controller_model",
            autospec=True,
        ) as mock_get_model,
        patch(
            "homeassistant.components.stiebel_eltron.config_flow.get_controller_model",
            new=mock_get_model,
        ),
    ):
        mock_get_model.return_value = ControllerModel.LWZ
        yield mock_get_model


@pytest.fixture(autouse=True)
def mock_lwz_api() -> Generator[MagicMock]:
    """Patch the LWZ API and return the mocked client."""

    with patch(
        "homeassistant.components.stiebel_eltron.coordinator.LwzStiebelEltronAPI",
        autospec=True,
    ) as mock_api_cls:
        api_client = MagicMock()

        api_client.get_target_temp = MagicMock(return_value=22.5)
        api_client.get_current_temp = MagicMock(return_value=21.0)
        api_client.get_current_humidity = MagicMock(return_value=45.0)
        api_client.get_operation = MagicMock(return_value=OperatingMode.AUTOMATIC)
        api_client.get_filter_alarm_status = MagicMock(return_value=False)

        api_client.connect = AsyncMock()
        api_client.close = AsyncMock()
        api_client.async_update = AsyncMock()
        api_client.set_operation = AsyncMock()
        api_client.set_target_temp = AsyncMock()

        api_client.is_connected = False
        api_client.host = "1.1.1.1"

        mock_api_cls.return_value = api_client
        yield api_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Stiebel Eltron",
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 502},
        entry_id="stiebel_eltron_001",
    )
