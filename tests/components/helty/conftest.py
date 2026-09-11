"""Common fixtures for the Helty Flow tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyhelty import FanMode, HeltyData
import pytest

from homeassistant.components.helty.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

DEVICE_NAME = "VMC Soggiorno"
HOST = "192.168.20.232"


def make_data(fan_mode: FanMode = FanMode.LOW) -> HeltyData:
    """Build a representative HeltyData snapshot."""
    return HeltyData(
        name=DEVICE_NAME,
        fan_mode=fan_mode,
        leds_on=True,
        indoor_temperature=28.1,
        outdoor_temperature=31.2,
        indoor_humidity=42.2,
        co2=0,
        filter_hours=0,
        light_level=0,
        raw_sensors=tuple([281, 312, 422] + [0] * 12),
        raw_status=tuple([int(fan_mode), 10] + [0] * 13),
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.helty.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_helty_client() -> Generator[AsyncMock]:
    """Mock a Helty client at both the integration and config flow import sites."""
    with (
        patch(
            "homeassistant.components.helty.HeltyClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.helty.config_flow.HeltyClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.async_get_name.return_value = DEVICE_NAME
        client.async_get_data.return_value = make_data()
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a configured Helty entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEVICE_NAME,
        data={CONF_HOST: HOST},
        entry_id="01HHHHHHHHHHHHHHHHHHHHHHHH",
    )
