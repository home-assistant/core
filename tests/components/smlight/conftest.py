"""Common fixtures for the SMLIGHT Zigbee tests."""

from collections.abc import Generator
from json import loads
from unittest.mock import AsyncMock, MagicMock, patch

from pysmlight.web import Info, Sensors
import pytest

from homeassistant.components.smlight.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "slzb-06.local",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "webtest",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.smlight.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_smlight_client() -> Generator[MagicMock]:
    """Mock the SMLIGHT API client."""
    with (
        patch(
            "homeassistant.components.smlight.coordinator.Api2", autospec=True
        ) as smlight_mock,
        patch("homeassistant.components.smlight.config_flow.Api2", new=smlight_mock),
    ):
        api = smlight_mock.return_value
        api.get_info.return_value = Info.from_dict(
            loads(load_fixture("info.json", DOMAIN))
        )
        api.get_sensors.return_value = Sensors.from_dict(
            loads(load_fixture("sensors.json", DOMAIN))
        )
        api.check_auth_needed.return_value = False
        api.authenticate.return_value = True
        yield api
