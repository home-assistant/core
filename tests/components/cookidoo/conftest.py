"""Common fixtures for the Cookidoo tests."""

from collections.abc import Generator
from typing import cast
from unittest.mock import AsyncMock, patch

from cookidoo_api import CookidooAuthResponse
import pytest

from homeassistant.components.cookidoo.const import CONF_LOCALIZATION, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry, load_json_object_fixture

EMAIL = "test-email"
PASSWORD = "test-password"
LOCALIZATION = "ch_de-ch"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.cookidoo.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_cookidoo_client() -> Generator[AsyncMock]:
    """Mock a Cookidoo client."""
    with (
        patch(
            "homeassistant.components.cookidoo.Cookidoo",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.cookidoo.config_flow.Cookidoo",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login.return_value = cast(CookidooAuthResponse, {"name": "Bring"})
        client.get_ingredients.return_value = load_json_object_fixture(
            "ingredients.json", DOMAIN
        )["data"]
        client.get_additional_items.return_value = load_json_object_fixture(
            "additional_items.json", DOMAIN
        )["data"]
        yield client


@pytest.fixture(name="cookidoo_config_entry")
def mock_cookidoo_config_entry() -> MockConfigEntry:
    """Mock cookidoo configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: EMAIL,
            CONF_PASSWORD: PASSWORD,
            CONF_LOCALIZATION: LOCALIZATION,
        },
        entry_id="01JBVVVJ87F6G5V0QJX6HBC94T",
    )
