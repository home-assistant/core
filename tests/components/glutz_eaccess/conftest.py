"""Fixtures for Glutz eAccess integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.glutz_eaccess.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)


@pytest.fixture
def ignore_missing_translations(request: pytest.FixtureRequest) -> list[str]:
    """Skip reauth translation keys (Lokalise-only) for auth_error tests."""
    if "auth_error" not in request.node.name:
        return []
    return [
        "component.homeassistant.issues.config_entry_reauth.title",
        "component.homeassistant.issues.config_entry_reauth.description",
    ]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "https://example.com",
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "secret",
        },
        unique_id="SYS1",
    )


@pytest.fixture
def mock_glutz_client() -> Generator[AsyncMock]:
    """Return a mocked GlutzAPI client."""
    with (
        patch(
            "homeassistant.components.glutz_eaccess.GlutzAPI",
            autospec=True,
        ) as client_mock,
        patch(
            "homeassistant.components.glutz_eaccess.config_flow.GlutzAPI",
            new=client_mock,
        ),
    ):
        client = client_mock.return_value
        client.get_access_points = AsyncMock(
            return_value=load_json_array_fixture("access_points.json", DOMAIN)
        )
        client.get_system_info = AsyncMock(
            return_value=load_json_object_fixture("system_info.json", DOMAIN)
        )
        client.open_access_point = AsyncMock(return_value=True)
        client.hold_open_access_point = AsyncMock(return_value=True)
        client.close_access_point = AsyncMock(return_value=True)
        yield client
