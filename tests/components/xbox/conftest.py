# type: ignore[reportArgumentType] # ignore JsonValueType assignment to pydantic model
"""Common fixtures for the Xbox tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pythonxbox.api.provider.catalog.models import CatalogResponse
from pythonxbox.api.provider.gameclips.models import GameclipsResponse
from pythonxbox.api.provider.people.models import PeopleResponse
from pythonxbox.api.provider.screenshots.models import ScreenshotResponse
from pythonxbox.api.provider.smartglass.models import (
    InstalledPackagesList,
    SmartglassConsoleList,
    SmartglassConsoleStatus,
)
from pythonxbox.api.provider.titlehub.models import TitleHubResponse

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.xbox.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), "cloud"
    )


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Xbox configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home Assistant Cloud",
        data={
            "auth_implementation": "cloud",
            "token": {
                "access_token": "1234567890",
                "expires_at": 1760697327.7298331,
                "expires_in": 3600,
                "refresh_token": "0987654321",
                "scope": "XboxLive.signin XboxLive.offline_access",
                "service": "xbox",
                "token_type": "bearer",
                "user_id": "AAAAAAAAAAAAAAAAAAAAA",
            },
        },
        unique_id="271958441785640",
    )


@pytest.fixture(name="authentication_manager")
def mock_authentication_manager() -> Generator[AsyncMock]:
    """Mock xbox-webapi AuthenticationManager."""

    with (
        patch(
            "homeassistant.components.xbox.config_flow.AuthenticationManager",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value

        yield client


@pytest.fixture(name="xbox_live_client")
def mock_xbox_live_client() -> Generator[AsyncMock]:
    """Mock xbox-webapi XboxLiveClient."""

    with (
        patch(
            "homeassistant.components.xbox.coordinator.XboxLiveClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.xbox.config_flow.XboxLiveClient", new=mock_client
        ),
    ):
        client = mock_client.return_value

        client.smartglass = AsyncMock()
        client.smartglass.get_console_list.return_value = SmartglassConsoleList(
            **load_json_object_fixture("smartglass_console_list.json", DOMAIN)
        )
        client.smartglass.get_console_status.return_value = SmartglassConsoleStatus(
            **load_json_object_fixture("smartglass_console_status.json", DOMAIN)
        )
        client.smartglass.get_installed_apps.return_value = InstalledPackagesList(
            **load_json_object_fixture("smartglass_installed_applications.json", DOMAIN)
        )

        client.catalog = AsyncMock()
        client.catalog.get_product_from_alternate_id.return_value = CatalogResponse(
            **load_json_object_fixture("catalog_product_lookup.json", DOMAIN)
        )
        client.catalog.get_products.return_value = CatalogResponse(
            **load_json_object_fixture("catalog_product_lookup.json", DOMAIN)
        )

        client.people = AsyncMock()
        client.people.get_friends_by_xuid.return_value = PeopleResponse(
            **load_json_object_fixture("people_batch.json", DOMAIN)
        )
        client.people.get_friends_own.return_value = PeopleResponse(
            **load_json_object_fixture("people_friends_own.json", DOMAIN)
        )

        client.titlehub = AsyncMock()
        client.titlehub.get_title_info.return_value = TitleHubResponse(
            **load_json_object_fixture("titlehub_titleinfo.json", DOMAIN)
        )
        client.titlehub.get_title_history.return_value = TitleHubResponse(
            **load_json_object_fixture("titlehub_titlehistory.json", DOMAIN)
        )
        client.gameclips = AsyncMock()
        client.gameclips.get_recent_clips_by_xuid.return_value = GameclipsResponse(
            **load_json_object_fixture("gameclips_recent_xuid.json", DOMAIN)
        )
        client.gameclips.get_recent_community_clips_by_title_id.return_value = (
            GameclipsResponse(
                **load_json_object_fixture(
                    "gameclips_community_recent_xuid.json", DOMAIN
                )
            )
        )
        client.screenshots = AsyncMock()
        client.screenshots.get_recent_screenshots_by_xuid.return_value = (
            ScreenshotResponse(
                **load_json_object_fixture("screenshots_recent_xuid.json", DOMAIN)
            )
        )
        client.screenshots.get_recent_community_screenshots_by_title_id.return_value = (
            ScreenshotResponse(
                **load_json_object_fixture(
                    "screenshots_community_recent_xuid.json", DOMAIN
                )
            )
        )

        client.xuid = "271958441785640"

        yield client
