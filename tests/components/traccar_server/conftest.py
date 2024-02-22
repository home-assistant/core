"""Common fixtures for the Traccar Server tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytraccar import ApiClient

from homeassistant.components.traccar_server.const import (
    CONF_CUSTOM_ATTRIBUTES,
    CONF_EVENTS,
    CONF_MAX_ACCURACY,
    CONF_SKIP_ACCURACY_FILTER_FOR,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)


@pytest.fixture
def mock_traccar_api_client() -> Generator[AsyncMock, None, None]:
    """Mock a Traccar ApiClient client."""
    with patch(
        "homeassistant.components.traccar_server.ApiClient",
        autospec=True,
    ) as mock_client, patch(
        "homeassistant.components.traccar_server.config_flow.ApiClient",
        new=mock_client,
    ):
        client: ApiClient = mock_client.return_value
        client.get_devices.return_value = load_json_array_fixture(
            "traccar_server/devices.json"
        )
        client.get_geofences.return_value = load_json_array_fixture(
            "traccar_server/geofences.json"
        )
        client.get_positions.return_value = load_json_array_fixture(
            "traccar_server/positions.json"
        )
        client.get_server.return_value = load_json_object_fixture(
            "traccar_server/server.json"
        )
        client.get_reports_events.return_value = load_json_array_fixture(
            "traccar_server/reports_events.json"
        )

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a Traccar Server config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="1.1.1.1:8082",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: "8082",
            CONF_USERNAME: "test@example.org",
            CONF_PASSWORD: "ThisIsNotThePasswordYouAreL00kingFor",
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
        options={
            CONF_CUSTOM_ATTRIBUTES: ["custom_attr_1"],
            CONF_EVENTS: ["device_moving"],
            CONF_MAX_ACCURACY: 5.0,
            CONF_SKIP_ACCURACY_FILTER_FOR: [],
        },
    )
