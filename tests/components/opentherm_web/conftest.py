"""Common fixtures for the OpenTherm Web tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from opentherm_web_api import OpenThermController
import pytest

from homeassistant.components.opentherm_web.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Pohorelice",
        domain=DOMAIN,
        data={"host": "example", "password": "secret"},
        unique_id="unique_thingy",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opentherm_web.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_opentherm():
    """Return a mocked OpenthermWebApi."""
    with patch(
        "homeassistant.components.opentherm_web.OpenThermWebApi"
    ) as mock_opentherm:
        web_api = mock_opentherm.return_value
        web_api.authenticate = Mock(return_value=True)

        controller = OpenThermController
        controller.device_id = 123
        web_api.get_controller = Mock(return_value=controller)

        yield web_api
