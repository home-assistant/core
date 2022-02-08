"""Fixtures for Cybro PLC integration tests."""

from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

from cybro import Device as CybroDevice
import pytest

from homeassistant.components.cybro.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.123", CONF_PORT: 4000, CONF_ADDRESS: 1000},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.cybro.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_cybro_config_flow(
    request: pytest.FixtureRequest,
) -> Generator[None, MagicMock, None]:
    """Return a mocked Cybro client."""
    with patch(
        "homeassistant.components.cybro.config_flow.Cybro", autospec=True
    ) as cybro_mock:
        cybro = cybro_mock.return_value
        cybro.update.return_value = CybroDevice(
            json.loads(load_fixture("cybro/device.json")), 1000
        )
        yield cybro
