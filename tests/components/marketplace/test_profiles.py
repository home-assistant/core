"""Tests for the download profiles of the Marketplace."""

from http import HTTPStatus
from pathlib import Path
import re
from typing import Any
from unittest.mock import patch

from aiohttp import ClientError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from yarl import URL

import homeassistant.components.marketplace as marketplace_integration
from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.const import CONF_PROFILE, DOMAIN
from homeassistant.components.marketplace.enums import RepositoryCategory
from homeassistant.components.marketplace.exceptions import (
    MarketplaceError,
    NotModifiedError,
)
from homeassistant.components.marketplace.profiles import (
    DEFAULT_PROFILE,
    PROFILE_ISSUE_PREFIX,
    DownloadProfile,
    get_profile,
)
from homeassistant.components.marketplace.system_health import system_health_info
from homeassistant.components.marketplace.utils.url import github_raw_file
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import (
    CategoryTestData,
    category_test_data_parametrized,
    get_marketplace,
    mocked_response,
)
from .conftest import MarketplaceResponses
from .const import REPOSITORY_PLUGIN, TOKEN

INTEGRATION_PATH = Path(marketplace_integration.__file__).parent

MIRROR_HOSTS = {
    "hamrelay.hasscn.top",
    "ghapi.hacs.vip",
    "ghrp2.hacs.vip",
    "ghrp.hacs.vip",
    "data-v2.hasscn.top",
    "data-v2.hacs.vip",
    "gh-proxy.org",
}

FILE = github_raw_file(repository="owner/repository", ref="main", path="file.txt")
FIRST_MIRROR = (
    f"https://hamrelay.hasscn.top/https://raw.githubusercontent.com/{FILE.path}"
)
SECOND_MIRROR = f"https://ghrp2.hacs.vip/raw/{FILE.path}"
THIRD_MIRROR = f"https://ghrp.hacs.vip/raw/{FILE.path}"

OTHER_FILE = github_raw_file(repository="owner/repository", ref="main", path="other")

CATALOG_MIRROR = "https://data-v2.hasscn.top/integration/data.json"
CATALOG_SECOND_MIRROR = "https://data-v2.hacs.vip/integration/data.json"
CATALOG_ORIGINAL = "https://data-v2.hacs.xyz/integration/data.json"

SLEEP = "homeassistant.components.marketplace.base.asyncio.sleep"
PROFILE_ISSUE_ID = f"{PROFILE_ISSUE_PREFIX}hasscn"

# Hosts outside profiles.py, none of them downloaded from
ALLOWED_HOSTS_IN_FILE = {
    # Links to the repository and its release, shown on the update entity
    "update.py": {"github.com"},
    # A comment pointing at the GitHub CLI issue
    "config_flow.py": {"github.com"},
}


def _requested_hosts(aioclient_mock: AiohttpClientMocker) -> set[str]:
    """Return the hosts the Marketplace sent requests to."""
    return {str(url.host) for _, url, _, _ in aioclient_mock.mock_calls}


def _catalog(last_fetched: int) -> dict[str, Any]:
    """Return an integration catalog fetched by the data service at a time."""
    return {
        "1": {
            "description": "A repository",
            "domain": "example",
            "etag_repository": "etag",
            "full_name": "owner/repository",
            "last_fetched": last_fetched,
            "last_updated": "2026-11-01T00:00:00Z",
            "last_version": "1.0.0",
            "manifest": {},
            "manifest_name": "Example",
        }
    }


def test_single_url_is_a_sequence() -> None:
    """Test an endpoint with one URL is tried like one with several."""
    profile = DownloadProfile(
        id="test",
        operator="Test",
        api="https://api.example.com",
        github="https://github.example.com",
        raw=("https://raw.example.com", "https://raw.example.org"),
        catalog="https://catalog.example.com",
    )

    assert profile.github == ("https://github.example.com",)
    assert profile.raw == ("https://raw.example.com", "https://raw.example.org")
    assert profile.catalog == ("https://catalog.example.com",)


@pytest.mark.parametrize("profile_id", [None, "", "removed_profile"])
def test_unknown_profile_is_the_default(profile_id: str | None) -> None:
    """Test a profile that is not set, or no longer exists, is the default."""
    assert get_profile(profile_id).id == DEFAULT_PROFILE


def test_no_hosts_outside_the_profiles() -> None:
    """Test the Marketplace names no host to download from outside profiles.py."""
    found: list[str] = []
    for path in sorted(INTEGRATION_PATH.rglob("*.py")):
        relative = path.relative_to(INTEGRATION_PATH).as_posix()
        if relative == "profiles.py":
            continue

        allowed = ALLOWED_HOSTS_IN_FILE.get(relative, set())
        found.extend(
            f"{relative}: {host}"
            for host in re.findall(r"https?://([^/\"'{}\s]+)", path.read_text())
            if host not in allowed
        )

    assert not found, "Hosts outside profiles.py:\n" + "\n".join(found)


@pytest.mark.usefixtures("init_integration")
async def test_default_profile_without_options(
    marketplace: MarketplaceManager, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an entry without a profile, every existing install, uses GitHub."""
    assert marketplace.configuration.profile.id == DEFAULT_PROFILE
    assert _requested_hosts(aioclient_mock) == {"data-v2.hacs.xyz"}


@pytest.mark.parametrize("download_profile", ["hasscn"])
async def test_china_profile_fetches_the_catalog_from_the_mirror(
    marketplace: MarketplaceManager, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the startup with the China profile only asks the mirrors.

    The catalog mirror only answers requests that name the Marketplace.
    """
    assert marketplace.configuration.profile.id == "hasscn"
    assert _requested_hosts(aioclient_mock) == {"data-v2.hasscn.top"}
    assert {
        headers["User-Agent"].split("/")[0]
        for _, _, _, headers in aioclient_mock.mock_calls
    } == {"HomeAssistantMarketplace"}


@pytest.mark.parametrize(
    ("download_profile", "host", "authorization"),
    [
        pytest.param(None, "api.github.com", f"token {TOKEN}", id="github"),
        pytest.param("hasscn", "hamrelay.hasscn.top", None, id="relay"),
    ],
)
async def test_github_token_only_goes_to_github(
    marketplace: MarketplaceManager,
    aioclient_mock: AiohttpClientMocker,
    host: str,
    authorization: str | None,
) -> None:
    """Test the API calls go to the profile, the token of the account only to GitHub."""
    aioclient_mock.mock_calls.clear()

    await marketplace.async_github_api_method(lambda api: api.rate_limit())

    assert [
        (url.host, headers.get("Authorization"))
        for _, url, _, headers in aioclient_mock.mock_calls
    ] == [(host, authorization)]


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize("download_profile", ["hasscn"])
async def test_api_falls_back_to_the_next_endpoint(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an API endpoint that can not be reached hands the calls over."""
    response_mocker.add(
        "https://hamrelay.hasscn.top/https://api.github.com/rate_limit",
        AiohttpClientMockResponse(
            "get",
            URL("https://hamrelay.hasscn.top/https://api.github.com/rate_limit"),
            exc=ClientError,
        ),
    )
    aioclient_mock.mock_calls.clear()

    response = await marketplace.async_github_api_method(lambda api: api.rate_limit())

    assert response.data.resources.core.limit
    assert [str(url) for _, url, _, _ in aioclient_mock.mock_calls] == [
        "https://hamrelay.hasscn.top/https://api.github.com/rate_limit",
        "https://ghapi.hacs.vip/rate_limit",
    ]
    assert "the Marketplace uses https://ghapi.hacs.vip" in caplog.text


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize("download_profile", ["hasscn"])
@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_install_from_the_catalog_through_the_mirrors(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    category_test_data: CategoryTestData,
) -> None:
    """Test an install with the China profile sends nothing to GitHub."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    aioclient_mock.mock_calls.clear()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repository/install", "repository": repository.data.id}
    )

    assert (await client.receive_json())["success"]
    assert repository.data.installed_version == category_test_data["version_base"]
    assert _requested_hosts(aioclient_mock) <= MIRROR_HOSTS


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize("download_profile", ["hasscn"])
async def test_release_assets_through_the_mirrors(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test release assets come from the mirror, not the URL the API names."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    asset_path = f"{REPOSITORY_PLUGIN}/releases/download/1.0.0/plugin-basic.js"
    asset_url = f"https://hamrelay.hasscn.top/https://github.com/{asset_path}"
    map_url = f"{asset_url}.map"
    release_url = (
        f"https://hamrelay.hasscn.top/https://api.github.com/repos/{REPOSITORY_PLUGIN}"
        "/releases/tags/1.0.0"
    )
    response_mocker.add(asset_url, mocked_response(asset_url, content=b"asset"))
    response_mocker.add(map_url, mocked_response(map_url, content=b"map"))
    response_mocker.add(
        release_url,
        mocked_response(
            release_url,
            json_content={
                "tag_name": "1.0.0",
                "assets": [
                    {
                        "name": "plugin-basic.js",
                        "browser_download_url": f"https://github.com/{asset_path}",
                    },
                    {
                        "name": "plugin-basic.js.map",
                        "browser_download_url": f"https://github.com/{asset_path}.map",
                    },
                ],
            },
        ),
    )
    aioclient_mock.mock_calls.clear()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repository/install", "repository": repository.data.id}
    )

    assert (await client.receive_json())["success"]
    assert repository.content.path.remote == "release"
    assert URL(map_url) in [url for _, url, _, _ in aioclient_mock.mock_calls]
    assert _requested_hosts(aioclient_mock) <= MIRROR_HOSTS


@pytest.mark.parametrize("download_profile", ["hasscn"])
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(
            AiohttpClientMockResponse("get", URL(FIRST_MIRROR), exc=TimeoutError),
            id="timeout",
        ),
        pytest.param(
            AiohttpClientMockResponse("get", URL(FIRST_MIRROR), exc=ClientError),
            id="connection_error",
        ),
        pytest.param(
            mocked_response(FIRST_MIRROR, status=HTTPStatus.TOO_MANY_REQUESTS),
            id="rate_limited",
        ),
        pytest.param(
            mocked_response(FIRST_MIRROR, status=HTTPStatus.BAD_GATEWAY),
            id="server_error",
        ),
        pytest.param(
            mocked_response(FIRST_MIRROR, status=HTTPStatus.NOT_FOUND),
            id="not_found",
        ),
    ],
)
async def test_download_falls_back_to_the_next_mirror(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    failure: AiohttpClientMockResponse,
) -> None:
    """Test a mirror that fails is skipped, and not tried first again."""
    response_mocker.add(FIRST_MIRROR, failure)
    response_mocker.add(
        SECOND_MIRROR, mocked_response(SECOND_MIRROR, content=b"mirrored")
    )
    other_url = f"https://ghrp2.hacs.vip/raw/{OTHER_FILE.path}"
    response_mocker.add(other_url, mocked_response(other_url, content=b"other"))
    aioclient_mock.mock_calls.clear()

    with patch(SLEEP) as sleep:
        assert await marketplace.async_download_file(FILE) == b"mirrored"
        assert await marketplace.async_download_file(OTHER_FILE) == b"other"

    # Another mirror is quicker than waiting for this one
    sleep.assert_not_called()
    assert [url for _, url, _, _ in aioclient_mock.mock_calls] == [
        URL(FIRST_MIRROR),
        URL(SECOND_MIRROR),
        URL(other_url),
    ]
    assert caplog.text.count("the Marketplace uses https://ghrp2.hacs.vip/raw") == 1


@pytest.mark.parametrize("download_profile", ["hasscn"])
async def test_download_falls_back_to_the_proxy(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test the public proxy is the last resort, it gets the full original URL."""
    for url in (FIRST_MIRROR, SECOND_MIRROR, THIRD_MIRROR):
        response_mocker.add(url, mocked_response(url, status=HTTPStatus.BAD_GATEWAY))
    proxied = f"https://gh-proxy.org/https://raw.githubusercontent.com/{FILE.path}"
    response_mocker.add(proxied, mocked_response(proxied, content=b"proxied"))

    assert await marketplace.async_download_file(FILE) == b"proxied"


@pytest.mark.parametrize("download_profile", ["hasscn"])
async def test_download_fails_when_every_mirror_fails(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test a file no mirror has gives nothing, the same as without mirrors."""
    proxied = f"https://gh-proxy.org/https://raw.githubusercontent.com/{FILE.path}"
    for url in (FIRST_MIRROR, SECOND_MIRROR, THIRD_MIRROR, proxied):
        response_mocker.add(
            url, mocked_response(url, status=HTTPStatus.NOT_FOUND), keep=True
        )

    assert await marketplace.async_download_file(FILE) is None


@pytest.mark.parametrize("download_profile", ["hasscn"])
async def test_catalog_falls_back_to_the_original(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test the catalog comes from the next endpoint when the mirrors fail."""
    for url in (CATALOG_MIRROR, CATALOG_SECOND_MIRROR):
        response_mocker.add(url, mocked_response(url, status=HTTPStatus.BAD_GATEWAY))
    response_mocker.add(
        CATALOG_ORIGINAL, mocked_response(CATALOG_ORIGINAL, json_content=_catalog(1))
    )

    assert await marketplace.data_client.async_get_category("integration")


@pytest.mark.parametrize("download_profile", ["hasscn"])
@pytest.mark.parametrize(
    ("method", "args", "section", "unusable", "usable"),
    [
        pytest.param(
            "async_get_category",
            ("integration",),
            "integration",
            {"error": "upstream unavailable"},
            _catalog(1),
            id="category",
        ),
        pytest.param(
            "async_get_removed",
            (),
            "removed",
            {"error": "upstream unavailable"},
            [{"repository": "owner/repository", "removal_type": "remove"}],
            id="list",
        ),
    ],
)
async def test_catalog_answer_that_is_unusable_falls_back(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    method: str,
    args: tuple[str, ...],
    section: str,
    unusable: dict[str, Any],
    usable: dict[str, Any] | list[dict[str, Any]],
) -> None:
    """Test a mirror answering JSON that is no catalog falls back to the next one."""
    mirror = f"https://data-v2.hasscn.top/{section}/data.json"
    second_mirror = f"https://data-v2.hacs.vip/{section}/data.json"
    response_mocker.add(mirror, mocked_response(mirror, json_content=unusable))
    response_mocker.add(
        second_mirror, mocked_response(second_mirror, json_content=usable)
    )

    assert await getattr(marketplace.data_client, method)(*args)


@pytest.mark.parametrize("download_profile", ["hasscn"])
async def test_catalog_that_fails_everywhere_raises_the_last_error(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test the catalog error is the one of the last endpoint, as without mirrors."""
    for url in (CATALOG_MIRROR, CATALOG_SECOND_MIRROR):
        response_mocker.add(url, mocked_response(url, status=HTTPStatus.BAD_GATEWAY))
    response_mocker.add(
        CATALOG_ORIGINAL, mocked_response(CATALOG_ORIGINAL, content=b"{not json")
    )

    with pytest.raises(MarketplaceError) as exc_info:
        await marketplace.data_client.async_get_category("integration")

    assert exc_info.value.translation_key == "catalog_invalid_json"


async def _unreachable_catalog(marketplace: MarketplaceManager) -> None:
    """Have the catalog of integrations fail once."""
    with patch.object(
        marketplace.data_client,
        "async_get_category",
        side_effect=MarketplaceError("no route to host"),
    ):
        await marketplace.async_get_category_repositories_from_catalog(
            RepositoryCategory.INTEGRATION
        )


@pytest.mark.parametrize(
    ("country", "download_profile", "suggested"),
    [
        pytest.param("CN", None, True, id="china"),
        pytest.param("NL", None, False, id="elsewhere"),
        pytest.param(None, None, False, id="no_country"),
        pytest.param("CN", "hasscn", False, id="already_active"),
    ],
)
async def test_profile_suggested_for_the_country(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    issue_registry: ir.IssueRegistry,
    country: str | None,
    suggested: bool,
) -> None:
    """Test a catalog out of reach suggests the profile meant for the country."""
    hass.config.country = country

    await _unreachable_catalog(marketplace)

    assert (
        issue_registry.async_get_issue(DOMAIN, PROFILE_ISSUE_ID) is not None
    ) is suggested


async def test_profile_suggestion_withdrawn_when_the_catalog_is_back(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the suggestion goes away once the catalog can be reached again."""
    hass.config.country = "CN"
    await _unreachable_catalog(marketplace)

    with patch.object(
        marketplace.data_client, "async_get_category", side_effect=NotModifiedError
    ):
        await marketplace.async_get_category_repositories_from_catalog(
            RepositoryCategory.INTEGRATION
        )

    assert issue_registry.async_get_issue(DOMAIN, PROFILE_ISSUE_ID) is None


async def test_profile_suggestion_fix_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    marketplace: MarketplaceManager,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test accepting the suggestion switches the profile and reloads."""
    assert await async_setup_component(hass, "repairs", {})
    hass.config.country = "CN"
    await _unreachable_catalog(marketplace)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, PROFILE_ISSUE_ID)

    assert data["type"] == "menu"
    assert data["menu_options"] == ["use_profile", "ignore"]
    assert data["description_placeholders"] == {
        "operator": get_profile("hasscn").operator
    }

    data = await process_repair_fix_flow(
        client, data["flow_id"], json={"next_step_id": "use_profile"}
    )
    await hass.async_block_till_done()

    assert data["type"] == "create_entry"
    assert init_integration.options == {CONF_PROFILE: "hasscn"}
    assert get_marketplace(hass) is not marketplace
    assert get_marketplace(hass).configuration.profile.id == "hasscn"
    assert issue_registry.async_get_issue(DOMAIN, PROFILE_ISSUE_ID) is None


async def test_profile_suggestion_ignored(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    marketplace: MarketplaceManager,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an ignored suggestion stays ignored, also after the catalog is back.

    Deleting the issue would forget the ignore, so it is left alone.
    """
    assert await async_setup_component(hass, "repairs", {})
    hass.config.country = "CN"
    await _unreachable_catalog(marketplace)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, PROFILE_ISSUE_ID)
    data = await process_repair_fix_flow(
        client, data["flow_id"], json={"next_step_id": "ignore"}
    )

    assert data["type"] == "abort"
    assert data["reason"] == "issue_ignored"
    assert init_integration.options == {}

    with patch.object(
        marketplace.data_client, "async_get_category", side_effect=NotModifiedError
    ):
        await marketplace.async_get_category_repositories_from_catalog(
            RepositoryCategory.INTEGRATION
        )
    await hass.config_entries.async_reload(init_integration.entry_id)
    await _unreachable_catalog(get_marketplace(hass))

    issue = issue_registry.async_get_issue(DOMAIN, PROFILE_ISSUE_ID)
    assert issue is not None
    assert issue.dismissed_version is not None


async def test_profile_suggestion_ignored_after_the_catalog_is_back(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    marketplace: MarketplaceManager,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test ignoring sticks when the catalog came back while the menu was open."""
    assert await async_setup_component(hass, "repairs", {})
    hass.config.country = "CN"
    await _unreachable_catalog(marketplace)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, PROFILE_ISSUE_ID)
    ir.async_delete_issue(hass, DOMAIN, PROFILE_ISSUE_ID)
    data = await process_repair_fix_flow(
        client, data["flow_id"], json={"next_step_id": "ignore"}
    )

    assert data["reason"] == "issue_ignored"
    issue = issue_registry.async_get_issue(DOMAIN, PROFILE_ISSUE_ID)
    assert issue is not None
    assert issue.dismissed_version is not None


@pytest.mark.parametrize("download_profile", ["hasscn"])
async def test_system_health_checks_the_mirrors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    marketplace: MarketplaceManager,
) -> None:
    """Test system health checks the endpoints of the active profile."""
    assert await async_setup_component(hass, "system_health", {})
    aioclient_mock.mock_calls.clear()

    with patch(
        "homeassistant.components.marketplace.system_health.system_health.async_check_can_reach_url",
        return_value="ok",
    ) as check:
        info = await system_health_info(hass)

    assert info["download_profile"] == "hasscn"
    assert [call.args[1] for call in check.call_args_list] == [
        "https://hamrelay.hasscn.top/https://api.github.com",
        "https://hamrelay.hasscn.top/https://raw.githubusercontent.com/hacs/default/main/integration",
        "https://hamrelay.hasscn.top/https://github.com/",
        "https://data-v2.hasscn.top/data.json",
    ]
