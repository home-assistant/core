"""Common fixtures for the wsdot tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.wsdot.const import (
    CONF_API_KEY,
    CONF_TRAVEL_TIMES,
    CONF_TRAVEL_TIMES_ID,
    CONF_TRAVEL_TIMES_NAME,
    DOMAIN,
)

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_data() -> dict[str, Any]:
    """Return valid test config data."""
    return {
        CONF_API_KEY: "foo",
        CONF_TRAVEL_TIMES: [{CONF_TRAVEL_TIMES_ID: 96, CONF_TRAVEL_TIMES_NAME: "I90 EB"}],
    }


@pytest.fixture
def mock_config_entry(mock_config_data) -> MockConfigEntry:
    """Mock a wsdot config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
    )

@pytest.fixture
def mock_wsdot_client() -> Generator[AsyncMock]:
    """Mock a wsdot client."""
    tt_routes = [load_json_object_fixture("wsdot.json", DOMAIN)]

    with patch(
            "homeassistant.components.wsdot.config_flow.WSDOTConfigFlow._fetch_wsdot",
        ) as wsdot_api:
        wsdot_api.return_value = tt_routes

        yield wsdot_api
