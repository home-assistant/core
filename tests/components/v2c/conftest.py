"""Common fixtures for the V2C tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytrydan.models.trydan import TrydanData

from homeassistant.components.v2c.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.helpers.json import json_dumps

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.v2c.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Define a config entry fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="da58ee91f38c2406c2a36d0a1a7f8569",
        title="EVSE 1.1.1.1",
        data={CONF_HOST: "1.1.1.1"},
    )


@pytest.fixture
def mock_v2c_client() -> Generator[AsyncMock]:
    """Mock a V2C client."""
    with (
        patch(
            "homeassistant.components.v2c.Trydan",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.v2c.config_flow.Trydan",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        get_data_json = load_json_object_fixture("get_data.json", DOMAIN)
        client.raw_data = {
            "content": json_dumps(get_data_json).encode("utf-8"),
            "status_code": 200,
        }
        client.get_data.return_value = TrydanData.from_api(get_data_json)
        client.data = client.get_data.return_value
        client.firmware_version = get_data_json["FirmwareVersion"]
        yield client
