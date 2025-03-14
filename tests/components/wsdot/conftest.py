"""Common fixtures for the wsdot tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.wsdot.config_flow import DOMAIN
from tests.common import load_json_object_fixture

@pytest.fixture
def mock_wsdot_client() -> Generator[AsyncMock]:
    """Mock a wsdot client."""
    tt_routes = load_json_object_fixture("wsdot.json", DOMAIN)
    # TODO - more accurate API response
    tt_routes = [tt_routes]

    with  patch(
            "homeassistant.components.wsdot.config_flow.WSDOTConfigFlow.fetch_wsdot",
        ) as wsdot_api:
        wsdot_api.return_value = tt_routes

        yield wsdot_api