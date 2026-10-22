"""NMBS tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyrail.models import (
    ConnectionsApiResponse,
    LiveboardApiResponse,
    StationsApiResponse,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.nmbs.const import (
    CONF_STATION_FROM,
    CONF_STATION_TO,
    DOMAIN,
)

STATION_FROM = "BE.NMBS.008812005"
STATION_TO = "BE.NMBS.008814001"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nmbs.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nmbs_client() -> Generator[AsyncMock]:
    """Mock a NMBS client."""
    with patch(
        "homeassistant.components.nmbs.coordinator.IRail", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.get_stations.return_value = StationsApiResponse.from_dict(
            load_json_object_fixture("stations.json", DOMAIN)
        )
        client.get_connections.return_value = ConnectionsApiResponse.from_dict(
            load_json_object_fixture("connections.json", DOMAIN)
        )
        liveboards = {
            STATION_FROM: LiveboardApiResponse.from_dict(
                load_json_object_fixture("liveboard.json", DOMAIN)
            ),
            STATION_TO: LiveboardApiResponse.from_dict(
                load_json_object_fixture("liveboard_zuid.json", DOMAIN)
            ),
        }
        client.get_liveboard.side_effect = lambda station_id: liveboards[station_id]
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Train from Brussel-Noord/Bruxelles-Nord to Brussel-Zuid/Bruxelles-Midi",
        data={
            CONF_STATION_FROM: STATION_FROM,
            CONF_STATION_TO: STATION_TO,
        },
        unique_id=f"{STATION_FROM}_{STATION_TO}",
    )
