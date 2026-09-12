"""Common fixtures for the Cookidoo tests."""

from collections.abc import Generator
from dataclasses import asdict
from unittest.mock import AsyncMock, patch

from cookidoo_api import (
    CookidooAdditionalItem,
    CookidooAuthData,
    CookidooIngredientItem,
    CookidooSubscription,
    CookidooUserInfo,
)
from cookidoo_api.types import CookidooCalendarDay, CookidooCalendarDayRecipe
import pytest

from homeassistant.components.cookidoo.const import DOMAIN
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_EMAIL,
    CONF_LANGUAGE,
    CONF_PASSWORD,
    CONF_TOKEN,
)

from tests.common import MockConfigEntry, load_json_object_fixture

EMAIL = "test-email"
PASSWORD = "test-password"
COUNTRY = "CH"
LANGUAGE = "de-CH"

TEST_UUID = "sub_uuid"

AUTH_DATA = CookidooAuthData(
    access_token="test-access-token",
    refresh_token="test-refresh-token",
    expires_at=1762000000.0,
)
STALE_AUTH_DATA = CookidooAuthData(
    access_token="stale-access-token",
    refresh_token="stale-refresh-token",
    expires_at=1761000000.0,
)


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
    with patch(
        "homeassistant.components.cookidoo.helpers.Cookidoo",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.login.return_value = None
        client.auth_data = AUTH_DATA
        client.apply_auth_data.side_effect = lambda auth_data: setattr(
            client, "auth_data", auth_data
        )
        client.get_ingredient_items.return_value = [
            CookidooIngredientItem(**item)
            for item in load_json_object_fixture("ingredient_items.json", DOMAIN)[
                "data"
            ]
        ]
        client.get_additional_items.return_value = [
            CookidooAdditionalItem(**item)
            for item in load_json_object_fixture("additional_items.json", DOMAIN)[
                "data"
            ]
        ]
        client.get_active_subscription.return_value = CookidooSubscription(
            **load_json_object_fixture("subscriptions.json", DOMAIN)["data"]
        )
        client.get_user_info.return_value = CookidooUserInfo(
            **load_json_object_fixture("user_info.json", DOMAIN)["data"]
        )
        client.get_recipes_in_calendar_week.return_value = [
            CookidooCalendarDay(
                id=day["id"],
                title=day["title"],
                recipes=[
                    CookidooCalendarDayRecipe(
                        id=recipe["id"],
                        name=recipe["name"],
                        total_time=recipe["total_time"],
                        thumbnail=recipe["thumbnail"],
                        image=recipe["image"],
                        url=recipe["url"],
                    )
                    for recipe in day["recipes"]
                ],
            )
            for day in load_json_object_fixture("calendar_week.json", DOMAIN)["data"]
        ]
        yield client


@pytest.fixture(name="cookidoo_config_entry")
def mock_cookidoo_config_entry() -> MockConfigEntry:
    """Mock cookidoo configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=3,
        data={
            CONF_EMAIL: EMAIL,
            CONF_PASSWORD: PASSWORD,
            CONF_COUNTRY: COUNTRY,
            CONF_LANGUAGE: LANGUAGE,
        },
        entry_id="01JBVVVJ87F6G5V0QJX6HBC94T",
        unique_id=TEST_UUID,
    )


@pytest.fixture(name="cookidoo_config_entry_with_token")
def mock_cookidoo_config_entry_with_token() -> MockConfigEntry:
    """Mock a cookidoo configuration entry holding persisted OAuth2 tokens."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=3,
        data={
            CONF_EMAIL: EMAIL,
            CONF_PASSWORD: PASSWORD,
            CONF_COUNTRY: COUNTRY,
            CONF_LANGUAGE: LANGUAGE,
            CONF_TOKEN: asdict(STALE_AUTH_DATA),
        },
        entry_id="01JBVVVJ87F6G5V0QJX6HBC94T",
        unique_id=TEST_UUID,
    )
