"""Common fixtures for the Cookidoo tests."""

from collections.abc import Callable, Generator
from dataclasses import asdict
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.fixture(name="mock_cookidoo")
def mock_cookidoo_class() -> Generator[MagicMock]:
    """Mock the Cookidoo class the integration instantiates."""
    with patch(
        "homeassistant.components.cookidoo.helpers.Cookidoo",
        autospec=True,
    ) as mock_client:
        yield mock_client


@pytest.fixture
def notify_auth_data_update(
    mock_cookidoo: MagicMock,
) -> Callable[[CookidooAuthData | None], None]:
    """Emulate the library notifying its consumer of new tokens.

    A token response without a refresh token leaves the library with nothing to
    hand over, which is what passing None stands for.
    """

    def _notify(auth_data: CookidooAuthData | None) -> None:
        if auth_data is None:
            return
        mock_cookidoo.return_value.auth_data = auth_data
        mock_cookidoo.call_args.kwargs["on_auth_data_update"](auth_data)

    return _notify


@pytest.fixture
def login_success(
    notify_auth_data_update: Callable[[CookidooAuthData | None], None],
) -> Callable[[], None]:
    """Emulate a successful login: fresh tokens, handed to the consumer."""

    def _login() -> None:
        notify_auth_data_update(AUTH_DATA)

    return _login


@pytest.fixture
def mock_cookidoo_client(
    mock_cookidoo: MagicMock,
    login_success: Callable[[], None],
) -> AsyncMock:
    """Mock a Cookidoo client."""
    client = mock_cookidoo.return_value
    # No tokens until a login provides them or the consumer restores them
    client.auth_data = None
    client.login.side_effect = login_success
    client.apply_auth_data.side_effect = lambda auth_data: setattr(
        client, "auth_data", auth_data
    )
    client.get_ingredient_items.return_value = [
        CookidooIngredientItem(**item)
        for item in load_json_object_fixture("ingredient_items.json", DOMAIN)["data"]
    ]
    client.get_additional_items.return_value = [
        CookidooAdditionalItem(**item)
        for item in load_json_object_fixture("additional_items.json", DOMAIN)["data"]
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
    return client


@pytest.fixture
def arrange_validation_tokens(
    mock_cookidoo_client: AsyncMock,
    notify_auth_data_update: Callable[[CookidooAuthData | None], None],
) -> Callable[[CookidooAuthData | None, CookidooAuthData | None], None]:
    """Arrange the tokens the config flow validation requests hand over.

    The login hands over the first, and the additional items fetch that follows
    it the second, which is how a request rotating the tokens mid-validation
    presents itself. Either can be None, for a response without a token.
    """

    def _arrange(
        login_tokens: CookidooAuthData | None,
        rotated_tokens: CookidooAuthData | None,
    ) -> None:
        mock_cookidoo_client.login.side_effect = lambda: notify_auth_data_update(
            login_tokens
        )

        async def _get_additional_items(*args: Any, **kwargs: Any) -> list:
            notify_auth_data_update(rotated_tokens)
            return []

        mock_cookidoo_client.get_additional_items.side_effect = _get_additional_items

    return _arrange


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
