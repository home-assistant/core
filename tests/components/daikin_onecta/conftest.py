"""Global fixtures for the Daikin Onecta integration."""
import json
import time
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import homeassistant.helpers.entity_registry as er
import pytest
from _pytest.assertion import truncate
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.single_file import SingleFileAmberSnapshotExtension
from syrupy.filters import props

from homeassistant.components.daikin_onecta.const import DAIKIN_API_URL
from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.coordinator import OnectaRuntimeData

truncate.DEFAULT_MAX_LINES = 9999
truncate.DEFAULT_MAX_CHARS = 9999

FAKE_REFRESH_TOKEN = "some-refresh-token"
FAKE_ACCESS_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
FAKE_AUTH_IMPL = "conftest-imported-cred"


def load_fixture_json(name):
    """Load a Daikin Onecta JSON fixture."""
    with open(f"tests/components/daikin_onecta/fixtures/{name}.json") as json_file:
        return json.load(json_file)



@pytest.mark.freeze_time("2026-01-01 12:00:00+00:00")
async def snapshot_platform_entities(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    platform: Platform,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fixture_device_json,
) -> None:
    """Snapshot entities and their states."""
    config_entry.runtime_data = OnectaRuntimeData(daikin_api=MagicMock(), devices={})
    config_entry.runtime_data.coordinator = MagicMock()
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ):
        aioclient_mock.get(DAIKIN_API_URL + "/v1/gateway-devices", status=200, json=load_fixture_json(fixture_device_json))
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)

    assert entity_entries

    entity_snapshot = {}
    for entity_entry in entity_entries:
        registry_data = dict(entity_entry.as_partial_dict)
        for key in ("config_entry_id", "created_at", "device_id", "id", "modified_at"):
            registry_data.pop(key, None)

        state = hass.states.get(entity_entry.entity_id)
        assert state is not None
        state_data = dict(state.as_dict())
        state_data.pop("last_changed", None)
        state_data.pop("last_reported", None)
        state_data.pop("last_updated", None)
        state_data.pop("context", None)

        entity_snapshot[entity_entry.entity_id] = {
            "entry": registry_data,
            "state": state_data,
        }

    assert entity_snapshot == snapshot(
        name=fixture_device_json,
        exclude=props("friendly_name"),
        extension_class=SingleFileAmberSnapshotExtension,
    )


@pytest.fixture(name="config_entry")
def mock_config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    mock_entry = MockConfigEntry(
        domain="daikin_onecta",
        data={
            "auth_implementation": "cloud",
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": FAKE_ACCESS_TOKEN,
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": 4102444800,
                "scope": 1,
            },
        },
    )
    mock_entry.add_to_hass(hass)

    return mock_entry


@pytest.fixture(name="onecta_auth")
def onecta_auth() -> None:
    """Provide the Onecta authentication fixture."""


@pytest.fixture(name="access_token")
def async_get_access_token() -> AsyncMock:
    """Restrict loaded platforms to list given."""

    with patch(
        "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
        return_value=FAKE_ACCESS_TOKEN,
    ):
        yield


@pytest.fixture(name="token_expiration_time")
def mock_token_expiration_time() -> float:
    """Fixture for expiration time of the config entry auth token."""
    return time.time() + 86400


@pytest.fixture(name="token_entry")
def mock_token_entry(token_expiration_time: float) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "refresh_token": FAKE_REFRESH_TOKEN,
        "access_token": FAKE_ACCESS_TOKEN,
        "type": "Bearer",
        "expires_at": token_expiration_time,
    }


@pytest.fixture(name="config_entry_v1_1")
def mock_config_entry_v1_1(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": FAKE_AUTH_IMPL,
            "token": token_entry,
        },
        minor_version=1,
    )
