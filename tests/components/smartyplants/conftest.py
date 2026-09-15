"""Fixtures for SmartyPlants tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from pysmartyplants import Sensor
import pytest

from homeassistant.components.smartyplants.const import CONF_WEBHOOK_SECRET, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_WEBHOOK_ID

from tests.common import MockConfigEntry, load_json_array_fixture

ACCOUNT_ID = "acct-0001"
API_KEY = "sp_test_key_12345678"
WEBHOOK_ID = "smartyplants_test_webhook"
WEBHOOK_SECRET = "top-secret"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.smartyplants.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a SmartyPlants config entry with a signed webhook."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SmartyPlants",
        data={
            CONF_API_KEY: API_KEY,
            CONF_WEBHOOK_ID: WEBHOOK_ID,
            CONF_WEBHOOK_SECRET: WEBHOOK_SECRET,
        },
        unique_id=ACCOUNT_ID,
    )


@pytest.fixture
def sensor_payloads() -> list[dict[str, Any]]:
    """Return the sensors endpoint payload, which tests may edit before polling."""
    return load_json_array_fixture("sensors.json", DOMAIN)


@pytest.fixture
def mock_smartyplants_client(
    sensor_payloads: list[dict[str, Any]],
) -> Generator[AsyncMock]:
    """Mock the SmartyPlants client wherever it is used."""
    with (
        patch(
            "homeassistant.components.smartyplants.SmartyPlantsClient", autospec=True
        ) as client_class,
        patch(
            "homeassistant.components.smartyplants.config_flow.SmartyPlantsClient",
            new=client_class,
        ),
    ):
        client = client_class.return_value
        client.async_verify.return_value = ACCOUNT_ID
        # Built at call time, so a test's edits to the payload reach the next poll.
        client.async_get_sensors.side_effect = lambda: [
            Sensor.from_api(payload) for payload in sensor_payloads
        ]
        yield client
