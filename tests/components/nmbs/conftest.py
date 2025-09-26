"""NMBS tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyrail.models import StationsApiResponse
import pytest

from homeassistant.components.nmbs.const import (
    CONF_STATION_FROM,
    CONF_STATION_TO,
    DOMAIN,
)

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nmbs.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nmbs_client() -> Generator[AsyncMock]:
    """Mock a NMBS client."""
    with (
        patch(
            "homeassistant.components.nmbs.iRail",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.nmbs.config_flow.iRail",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_stations.return_value = StationsApiResponse.from_dict(
            load_json_object_fixture("stations.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Train from Brussel-Noord/Bruxelles-Nord to Brussel-Zuid/Bruxelles-Midi",
        data={
            CONF_STATION_FROM: "BE.NMBS.008812005",
            CONF_STATION_TO: "BE.NMBS.008814001",
        },
        unique_id="BE.NMBS.008812005_BE.NMBS.008814001",
    )
