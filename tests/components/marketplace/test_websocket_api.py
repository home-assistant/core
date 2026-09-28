"""Tests for the Marketplace WebSocket API."""

import asyncio
from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.const import (
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    WARNING_REMINDER_INTERVAL,
)
from homeassistant.components.marketplace.enums import (
    MarketplaceSignal,
    RepositoryCategory,
)
from homeassistant.components.marketplace.exceptions import MarketplaceError
from homeassistant.components.marketplace.repositories.base import RepositoryManifest
from homeassistant.components.marketplace.utils.storage import async_save_to_storage
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_SYSTEM,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.const import CONF_TOKEN, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import get_marketplace, github_api_calls, mocked_response
from .conftest import MarketplaceResponses
from .const import (
    FROZEN_TIME,
    REPOSITORY_INTEGRATION,
    REPOSITORY_INTEGRATION_ID,
    TOKEN,
    WARNING_ACCEPTANCE,
)

from tests.common import MockConfigEntry, MockUser
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator

CRITICAL_REPOSITORY = {
    "repository": "critical/repository",
    "reason": "It eats your configuration",
    "link": "https://example.com/critical",
    "acknowledged": False,
}

# One valid message per registered command, used to check the admin requirement.
COMMANDS: tuple[dict[str, Any], ...] = (
    {"type": "marketplace/info"},
    {"type": "marketplace/github/connect"},
    {"type": "marketplace/warning/accept"},
    {"type": "marketplace/subscribe", "signal": MarketplaceSignal.REPOSITORY},
    {"type": "marketplace/critical/list"},
    {"type": "marketplace/critical/acknowledge", "repository": REPOSITORY_INTEGRATION},
    {"type": "marketplace/repositories/list"},
    {"type": "marketplace/repositories/removed"},
    {"type": "marketplace/repositories/clear_new"},
    {
        "type": "marketplace/repositories/add",
        "repository": REPOSITORY_INTEGRATION,
        "category": "integration",
    },
    {
        "type": "marketplace/repositories/remove",
        "repository": REPOSITORY_INTEGRATION_ID,
    },
    {"type": "marketplace/repository/info", "repository_id": REPOSITORY_INTEGRATION_ID},
    {
        "type": "marketplace/repository/download",
        "repository": REPOSITORY_INTEGRATION_ID,
    },
    {"type": "marketplace/repository/ignore", "repository": REPOSITORY_INTEGRATION_ID},
    {
        "type": "marketplace/repository/state",
        "repository": REPOSITORY_INTEGRATION_ID,
        "state": "other",
    },
    {
        "type": "marketplace/repository/version",
        "repository": REPOSITORY_INTEGRATION_ID,
        "version": "1.0.0",
    },
    {
        "type": "marketplace/repository/beta",
        "repository": REPOSITORY_INTEGRATION_ID,
        "show_beta": True,
    },
    {"type": "marketplace/repository/refresh", "repository": REPOSITORY_INTEGRATION_ID},
    {
        "type": "marketplace/repository/release_notes",
        "repository": REPOSITORY_INTEGRATION_ID,
    },
    {"type": "marketplace/repository/remove", "repository": REPOSITORY_INTEGRATION_ID},
    {
        "type": "marketplace/repository/releases",
        "repository_id": REPOSITORY_INTEGRATION_ID,
    },
)

# The commands that work without a loaded Marketplace.
COMMANDS_WITHOUT_MARKETPLACE = {
    "marketplace/critical/acknowledge",
    "marketplace/critical/list",
    "marketplace/subscribe",
}

# The commands that need a GitHub connection, with a valid message.
GITHUB_COMMANDS: tuple[dict[str, Any], ...] = (
    {
        "type": "marketplace/repositories/add",
        "repository": "hacs-test-org/integration-basic-custom",
        "category": "integration",
    },
)

# The commands that reach GitHub anonymously without a connection. Downloading
# the version the catalog names skips the API, so the download picks another.
ANONYMOUS_GITHUB_COMMANDS: tuple[dict[str, Any], ...] = (
    {
        "type": "marketplace/repository/download",
        "repository": REPOSITORY_INTEGRATION_ID,
        "version": "2.0.0",
    },
    {
        "type": "marketplace/repository/version",
        "repository": REPOSITORY_INTEGRATION_ID,
        "version": "1.0.0",
    },
    {
        "type": "marketplace/repository/beta",
        "repository": REPOSITORY_INTEGRATION_ID,
        "show_beta": True,
    },
    {"type": "marketplace/repository/refresh", "repository": REPOSITORY_INTEGRATION_ID},
)

# The commands that need the first-run warning accepted, with a valid message.
WARNING_COMMANDS: tuple[dict[str, Any], ...] = (
    {
        "type": "marketplace/repository/download",
        "repository": REPOSITORY_INTEGRATION_ID,
    },
    {
        "type": "marketplace/repository/version",
        "repository": REPOSITORY_INTEGRATION_ID,
        "version": "1.0.0",
    },
    {
        "type": "marketplace/repository/beta",
        "repository": REPOSITORY_INTEGRATION_ID,
        "show_beta": True,
    },
    {
        "type": "marketplace/repositories/add",
        "repository": "hacs-test-org/integration-basic-custom",
        "category": "integration",
    },
)

# The commands that work before the first-run warning is accepted.
COMMANDS_WITHOUT_WARNING: tuple[dict[str, Any], ...] = (
    {"type": "marketplace/info"},
    {"type": "marketplace/repositories/list"},
    {"type": "marketplace/repository/info", "repository_id": REPOSITORY_INTEGRATION_ID},
    {"type": "marketplace/repository/refresh", "repository": REPOSITORY_INTEGRATION_ID},
    {
        "type": "marketplace/repository/releases",
        "repository_id": REPOSITORY_INTEGRATION_ID,
    },
    {"type": "marketplace/repository/remove", "repository": REPOSITORY_INTEGRATION_ID},
    {"type": "marketplace/github/connect"},
)

RATE_LIMITED = {"message": "API rate limit exceeded for 127.0.0.1."}


def translated_error(
    code: str, translation_key: str, message: str, **placeholders: str
) -> dict[str, Any]:
    """Return an error the Marketplace answers with, translated for the panel."""
    return {
        "code": code,
        "message": message,
        "translation_key": translation_key,
        "translation_domain": DOMAIN,
        "translation_placeholders": placeholders or None,
    }


# Every command that resolves a repository by id, with the field it uses.
REPOSITORY_COMMANDS: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("marketplace/repository/info", "repository_id", {}),
    ("marketplace/repository/download", "repository", {}),
    ("marketplace/repository/ignore", "repository", {}),
    ("marketplace/repository/state", "repository", {"state": "other"}),
    ("marketplace/repository/version", "repository", {"version": "1.0.0"}),
    ("marketplace/repository/beta", "repository", {"show_beta": True}),
    ("marketplace/repository/refresh", "repository", {}),
    ("marketplace/repository/release_notes", "repository", {}),
    ("marketplace/repository/remove", "repository", {}),
    ("marketplace/repository/releases", "repository_id", {}),
    ("marketplace/repositories/remove", "repository", {}),
    ("marketplace/repositories/clear_new", "repository", {}),
)


@pytest.mark.parametrize(
    "message", [pytest.param(command, id=command["type"]) for command in COMMANDS]
)
@pytest.mark.usefixtures("init_integration")
async def test_commands_require_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    message: dict[str, Any],
) -> None:
    """Test that every command is refused for a non admin user."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json_auto_id(message)
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    ("command", "field", "extra"),
    [
        pytest.param(command, field, extra, id=command)
        for command, field, extra in REPOSITORY_COMMANDS
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_unknown_repository(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    command: str,
    field: str,
    extra: dict[str, Any],
) -> None:
    """Test that every repository command reports an unknown repository."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": command, field: "0", **extra})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == translated_error(
        "repository_not_found",
        "repository_not_found",
        "The Marketplace does not know the repository with ID 0",
        repository="0",
    )


@pytest.mark.usefixtures("init_integration")
async def test_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the information about the Marketplace itself."""
    client = await hass_ws_client(hass)
    freezer.move_to(WARNING_ACCEPTANCE["accepted_at"])

    await client.send_json_auto_id({"type": "marketplace/info"})
    response = await client.receive_json()

    assert response["success"]
    # The categories are a set, so they are asserted separately in their own test
    assert response["result"] | {"categories": None} == {
        "categories": None,
        "debug": False,
        "disabled_reason": None,
        "github_connected": True,
        "has_pending_tasks": False,
        "lovelace_mode": "storage",
        "stage": "running",
        "startup": False,
        "version": HA_VERSION,
        "warning_accepted": True,
        "warning_reminder_due": False,
    }


async def test_info_follows_the_loaded_entry(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test the commands registered at start keep working across a reload."""
    client = await hass_ws_client(hass)

    assert await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "marketplace/info"})
    assert (await client.receive_json())["success"]

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "marketplace/info"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == translated_error(
        "not_loaded", "not_loaded", "The Marketplace is not loaded"
    )


@pytest.mark.usefixtures("init_integration")
async def test_subscribe(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that a subscription forwards the Marketplace events."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "marketplace/subscribe", "signal": MarketplaceSignal.REPOSITORY}
    )
    assert (await client.receive_json())["success"]

    async_dispatcher_send(
        hass, MarketplaceSignal.REPOSITORY, {"action": "update", "id": 1337}
    )

    response = await client.receive_json()
    assert response["type"] == "event"
    assert response["event"] == {"action": "update", "id": 1337}


@pytest.mark.usefixtures("init_integration")
async def test_repository_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the information about a single repository."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/info",
            "repository_id": REPOSITORY_INTEGRATION_ID,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == snapshot(exclude=props("local_path"))


@pytest.mark.parametrize(
    ("domain", "replaces_built_in"),
    [
        pytest.param("light", True, id="built_in"),
        pytest.param("example", False, id="custom"),
        pytest.param(None, False, id="no_domain"),
    ],
)
async def test_repository_info_replaces_built_in(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    domain: str | None,
    replaces_built_in: bool,
) -> None:
    """Test the information tells when an integration takes a built-in domain."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.domain = domain
    repository.updated_info = True

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/info",
            "repository_id": REPOSITORY_INTEGRATION_ID,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["replaces_built_in"] is replaces_built_in


async def test_repository_info_clears_new(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that looking at a repository stops it from being new."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.new = True

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/info",
            "repository_id": REPOSITORY_INTEGRATION_ID,
        }
    )
    assert (await client.receive_json())["success"]

    assert repository.data.new is False


async def test_repository_info_survives_a_broken_update(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a repository that can not be refreshed still reports back."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    client = await hass_ws_client(hass)
    with patch.object(
        repository, "update_repository", side_effect=MarketplaceError("Nope")
    ):
        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/info",
                "repository_id": REPOSITORY_INTEGRATION_ID,
            }
        )
        response = await client.receive_json()

    assert response["success"]
    assert "Nope" in caplog.text


async def test_repositories_list(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test listing every known repository."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "marketplace/repositories/list"})
    response = await client.receive_json()

    assert response["success"]
    assert {repository["full_name"] for repository in response["result"]} == {
        repository.data.full_name for repository in marketplace.repositories.list_all
    }


@pytest.mark.usefixtures("init_integration")
async def test_repositories_list_by_category(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing the repositories of a single category."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "marketplace/repositories/list", "categories": ["integration"]}
    )
    response = await client.receive_json()

    assert response["success"]
    assert [repository["full_name"] for repository in response["result"]] == [
        REPOSITORY_INTEGRATION
    ]


async def test_repositories_list_ignores_country(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a repository with a country in its hacs.json is listed regardless."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.repository_manifest = RepositoryManifest.from_dict(
        {"name": "Basic integration", "country": ["NO"]}
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "marketplace/repositories/list"})
    response = await client.receive_json()

    assert response["success"]
    listed = next(
        item
        for item in response["result"]
        if item["full_name"] == REPOSITORY_INTEGRATION
    )
    assert "country" not in listed


async def test_repositories_removed(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test listing the repositories that were removed from the Marketplace."""
    removed = marketplace.repositories.removed_repository("removed/repository")
    removed.update_data({"reason": "Gone", "removal_type": "remove"})

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "marketplace/repositories/removed"})
    response = await client.receive_json()

    assert response["success"]
    assert {"repository": "removed/repository", "reason": "Gone"}.items() <= next(
        entry
        for entry in response["result"]
        if entry["repository"] == "removed/repository"
    ).items()


async def test_repositories_removed_skips_ignored(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that an ignored repository is not reported as removed."""
    marketplace.repositories.removed_repository("removed/repository")
    marketplace.common.ignored_repositories.add("removed/repository")

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "marketplace/repositories/removed"})
    response = await client.receive_json()

    assert response["success"]
    assert "removed/repository" not in [
        entry["repository"] for entry in response["result"]
    ]


async def test_repositories_clear_new_for_categories(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test clearing the new flag of a whole category."""
    integration = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    plugin = marketplace.repositories.get_by_full_name("hacs-test-org/plugin-basic")
    integration.data.new = True
    plugin.data.new = True

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repositories/clear_new", "categories": ["integration"]}
    )
    assert (await client.receive_json())["success"]

    assert integration.data.new is False
    assert plugin.data.new is True


async def test_repositories_clear_new_for_one_repository(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test clearing the new flag of a single repository."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.new = True

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repositories/clear_new",
            "repository": REPOSITORY_INTEGRATION_ID,
        }
    )
    assert (await client.receive_json())["success"]

    assert repository.data.new is False


@pytest.mark.usefixtures("init_integration")
async def test_repositories_add_existing(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test adding a repository the Marketplace already knows is answered."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repositories/add",
            "repository": REPOSITORY_INTEGRATION,
            "category": "integration",
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == translated_error(
        "repository_exists",
        "repository_exists",
        f"{REPOSITORY_INTEGRATION} is already in the Marketplace",
        repository=REPOSITORY_INTEGRATION,
    )


@pytest.mark.usefixtures("init_integration")
async def test_repositories_add_unknown_category(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test adding a repository to a category that is not active is refused."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repositories/add",
            "repository": "test/test",
            "category": "netdaemon",
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == translated_error(
        "invalid_format",
        "invalid_category",
        "Repositories cannot be added to the netdaemon category",
        category="netdaemon",
    )
    assert get_marketplace(hass).repositories.get_by_full_name("test/test") is None


@pytest.mark.usefixtures("init_integration")
async def test_repositories_add_invalid_url(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that a URL no repository can be read from is answered."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repositories/add",
            "repository": "https://example.com/",
            "category": "integration",
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == translated_error(
        "invalid_format",
        "invalid_repository",
        "Could not read a GitHub repository from https://example.com/",
        repository="https://example.com/",
    )


async def test_repositories_remove(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test unregistering a repository from the Marketplace."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repositories/remove",
            "repository": REPOSITORY_INTEGRATION_ID,
        }
    )
    assert (await client.receive_json())["success"]

    assert marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID) is None


async def test_repositories_remove_refuses_downloaded(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a downloaded repository is not forgotten while its files stay."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed = True
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repositories/remove",
            "repository": REPOSITORY_INTEGRATION_ID,
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "repository_downloaded"
    assert marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID) is repository


async def test_repository_ignore(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test ignoring a repository."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/ignore",
            "repository": REPOSITORY_INTEGRATION_ID,
        }
    )
    assert (await client.receive_json())["success"]

    assert REPOSITORY_INTEGRATION in marketplace.common.ignored_repositories


async def test_repository_state(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test setting the state the frontend shows for a repository."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/state",
            "repository": REPOSITORY_INTEGRATION_ID,
            "state": "other",
        }
    )
    assert (await client.receive_json())["success"]

    assert (
        marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID).state == "other"
    )


async def test_repository_version(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test pinning a repository to a version."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    client = await hass_ws_client(hass)
    with patch.object(repository, "update_repository"):
        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/version",
                "repository": REPOSITORY_INTEGRATION_ID,
                "version": "1.5.0",
            }
        )
        assert (await client.receive_json())["success"]

    assert repository.data.selected_tag == "1.5.0"
    assert repository.state is None


async def test_repository_version_default_branch(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that selecting the default branch stops pinning the repository."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    await repository.update_repository(force=True)
    assert repository.data.default_branch == "main"

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/version",
            "repository": REPOSITORY_INTEGRATION_ID,
            "version": "main",
        }
    )
    assert (await client.receive_json())["success"]

    assert repository.data.selected_tag is None


async def test_repository_beta(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test opting a repository in to pre-releases."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/beta",
            "repository": REPOSITORY_INTEGRATION_ID,
            "show_beta": True,
        }
    )
    assert (await client.receive_json())["success"]

    assert marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID).data.show_beta


async def test_repository_refresh(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test refreshing a single repository."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    client = await hass_ws_client(hass)
    with patch.object(
        repository, "update_repository", wraps=repository.update_repository
    ) as update:
        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/refresh",
                "repository": REPOSITORY_INTEGRATION_ID,
            }
        )
        assert (await client.receive_json())["success"]

    assert update.call_args.kwargs == {"ignore_issues": True, "force": True}


async def test_repository_download(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test downloading a repository."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/download",
            "repository": REPOSITORY_INTEGRATION_ID,
        }
    )
    assert (await client.receive_json())["success"]

    assert marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID).data.installed


async def test_repository_download_failure(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a download that can not be completed."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    client = await hass_ws_client(hass)
    with patch.object(
        repository,
        "async_download_repository",
        side_effect=MarketplaceError("Could not download"),
    ):
        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/download",
                "repository": REPOSITORY_INTEGRATION_ID,
            }
        )
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == translated_error(
        "error",
        "download_failed",
        f"Downloading {REPOSITORY_INTEGRATION} failed: Could not download",
        repository=REPOSITORY_INTEGRATION,
        error="Could not download",
    )


async def test_repository_remove(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test removing a downloaded repository."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/download",
            "repository": REPOSITORY_INTEGRATION_ID,
        }
    )
    assert (await client.receive_json())["success"]

    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/remove",
            "repository": REPOSITORY_INTEGRATION_ID,
        }
    )
    assert (await client.receive_json())["success"]

    assert repository.data.installed is False


async def test_repository_release_notes(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the release notes of the versions newer than the downloaded one."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    await repository.update_repository(force=True)
    repository.data.installed_version = "0.9.0"

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/release_notes",
            "repository": REPOSITORY_INTEGRATION_ID,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert [entry["tag"] for entry in response["result"]] == ["1.0.0"]


async def test_repository_release_notes_without_a_download(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that a repository that is not downloaded lists every release."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    await repository.update_repository(force=True)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/release_notes",
            "repository": REPOSITORY_INTEGRATION_ID,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert [entry["tag"] for entry in response["result"]] == ["1.0.0"]


async def test_repository_releases(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test listing the releases of a repository."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/releases",
            "repository_id": REPOSITORY_INTEGRATION_ID,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert [entry["tag"] for entry in response["result"]] == [
        "3.0.0",
        "2.5.0",
        "2.0.0",
        "1.0.0",
    ]


async def test_repository_releases_failure(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test releases that can not be fetched."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    client = await hass_ws_client(hass)
    with patch.object(
        repository, "async_get_releases", side_effect=MarketplaceError("Rate limited")
    ):
        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/releases",
                "repository_id": REPOSITORY_INTEGRATION_ID,
            }
        )
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == translated_error(
        "unknown",
        "releases_failed",
        f"Could not get the releases of {REPOSITORY_INTEGRATION}: Rate limited",
        repository=REPOSITORY_INTEGRATION,
        error="Rate limited",
    )


@pytest.mark.usefixtures("init_integration")
async def test_critical_list_without_data(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing critical repositories before any were stored."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "marketplace/critical/list"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == []


@pytest.mark.usefixtures("init_integration")
async def test_critical_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing the stored critical repositories."""
    await async_save_to_storage(hass, "critical", [CRITICAL_REPOSITORY])

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "marketplace/critical/list"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == [CRITICAL_REPOSITORY]


@pytest.mark.usefixtures("init_integration")
async def test_critical_acknowledge(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test acknowledging a critical repository."""
    await async_save_to_storage(hass, "critical", [CRITICAL_REPOSITORY])

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/critical/acknowledge",
            "repository": "critical/repository",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == [CRITICAL_REPOSITORY | {"acknowledged": True}]


@pytest.mark.usefixtures("init_integration")
async def test_critical_acknowledge_unknown_repository(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test acknowledging a repository that is not critical."""
    await async_save_to_storage(hass, "critical", [CRITICAL_REPOSITORY])

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/critical/acknowledge", "repository": "other/repository"}
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == [CRITICAL_REPOSITORY]


@pytest.mark.usefixtures("init_integration")
async def test_critical_acknowledge_without_a_repository(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the command needs to know what to acknowledge."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "marketplace/critical/acknowledge"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


@pytest.mark.usefixtures("init_integration")
async def test_registered_commands(hass: HomeAssistant) -> None:
    """Test that every Marketplace command is registered on the connection."""
    handlers = hass.data["websocket_api"]

    assert sorted(
        command for command in handlers if command.startswith(f"{DOMAIN}/")
    ) == sorted({command["type"] for command in COMMANDS})


@pytest.mark.usefixtures("init_integration")
async def test_categories_are_reported(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the active categories are part of the Marketplace information."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "marketplace/info"})
    response = await client.receive_json()

    assert set(response["result"]["categories"]) == {
        RepositoryCategory.INTEGRATION,
        RepositoryCategory.PLUGIN,
        RepositoryCategory.TEMPLATE,
        RepositoryCategory.THEME,
    }


@pytest.mark.parametrize(
    "message",
    [
        pytest.param(command, id=command["type"])
        for command in COMMANDS
        if command["type"] not in COMMANDS_WITHOUT_MARKETPLACE
    ],
)
async def test_commands_before_the_marketplace_is_loaded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    message: dict[str, Any],
) -> None:
    """Test the commands answer while there is no loaded Marketplace."""
    MockConfigEntry(
        domain=DOMAIN, data={}, disabled_by=ConfigEntryDisabler.USER
    ).add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(message)
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == translated_error(
        "not_loaded", "not_loaded", "The Marketplace is not loaded"
    )


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.usefixtures("init_integration")
async def test_info_without_github(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the information tells the panel no GitHub account is connected."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "marketplace/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["github_connected"] is False
    assert response["result"]["disabled_reason"] is None


@pytest.mark.parametrize(
    "message",
    [pytest.param(command, id=command["type"]) for command in GITHUB_COMMANDS],
)
@pytest.mark.parametrize("github_token", [None])
@pytest.mark.usefixtures("init_integration")
async def test_commands_need_github(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    message: dict[str, Any],
) -> None:
    """Test the commands that need a GitHub connection are refused."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(message)
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == translated_error(
        "github_not_connected",
        "github_not_connected",
        "Connect a GitHub account to the Marketplace first",
    )
    assert not github_api_calls(aioclient_mock)


@pytest.mark.parametrize("github_token", [None])
async def test_connect_github(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: MockConfigEntry,
    github_device_client: AsyncMock,
    device_activation_event: asyncio.Event,
    warning_accepted: dict[str, Any],
) -> None:
    """Test connecting a GitHub account from the panel."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "marketplace/github/connect"})
    response = await client.receive_json()

    assert response["success"]
    flow_id = response["result"]["flow_id"]

    flow = hass.config_entries.flow.async_get(flow_id)
    assert flow["context"]["source"] == SOURCE_RECONFIGURE
    assert flow["context"]["entry_id"] == init_integration.entry_id
    assert flow["step_id"] == "device"

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.data == {
        CONF_TOKEN: TOKEN,
        CONF_WARNING_ACCEPTED: warning_accepted,
    }
    assert init_integration.state is ConfigEntryState.LOADED

    await client.send_json_auto_id({"type": "marketplace/info"})
    response = await client.receive_json()

    assert response["result"]["github_connected"] is True


@pytest.mark.parametrize(
    "message",
    [
        pytest.param(command, id=command["type"])
        for command in ANONYMOUS_GITHUB_COMMANDS
    ],
)
@pytest.mark.parametrize("github_token", [None])
async def test_commands_without_github(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    message: dict[str, Any],
) -> None:
    """Test downloading and updating work without a GitHub connection."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(message)
    response = await client.receive_json()

    assert response["success"]
    assert not marketplace.system.disabled


@pytest.mark.parametrize(
    "message",
    [
        pytest.param(command, id=command["type"])
        for command in ANONYMOUS_GITHUB_COMMANDS
    ],
)
@pytest.mark.parametrize(
    "url",
    [
        pytest.param(
            f"https://api.github.com/repos/{REPOSITORY_INTEGRATION}", id="repository"
        ),
        pytest.param(
            f"https://api.github.com/repos/{REPOSITORY_INTEGRATION}/releases",
            id="releases",
        ),
    ],
)
@pytest.mark.parametrize(
    "status",
    [
        pytest.param(HTTPStatus.FORBIDDEN, id="403"),
        pytest.param(HTTPStatus.TOO_MANY_REQUESTS, id="429"),
    ],
)
@pytest.mark.parametrize("github_token", [None])
async def test_commands_rate_limited_without_github(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
    message: dict[str, Any],
    url: str,
    status: HTTPStatus,
) -> None:
    """Test running out of anonymous requests fails only that one action."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.releases = True
    response_mocker.add(
        url,
        mocked_response(url, status=status, json_content=RATE_LIMITED),
        keep=True,
    )
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(message)
    response = await client.receive_json()
    await hass.async_block_till_done()

    assert not response["success"]
    assert response["error"]["code"] == "github_rate_limited"
    assert not marketplace.system.disabled
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    # Nothing the action set out to change sticks
    assert repository.data.releases is True
    assert repository.data.selected_tag is None
    assert repository.data.show_beta is False
    assert repository.data.installed is False


@pytest.mark.parametrize("github_token", [None])
async def test_repository_releases_rate_limited_without_github(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
) -> None:
    """Test running out of anonymous requests answers clearly and disables nothing."""
    url = f"https://api.github.com/repos/{REPOSITORY_INTEGRATION}/releases"
    response_mocker.add(
        url,
        mocked_response(url, status=HTTPStatus.FORBIDDEN, json_content=RATE_LIMITED),
    )
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/releases",
            "repository_id": REPOSITORY_INTEGRATION_ID,
        }
    )
    response = await client.receive_json()
    await hass.async_block_till_done()

    assert not response["success"]
    assert response["error"]["code"] == "github_rate_limited"
    assert not marketplace.system.disabled
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize("github_token", [None])
async def test_repository_info_rate_limited_without_github(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
) -> None:
    """Test the repository page still answers when the anonymous limit ran out."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.releases = True

    url = f"https://api.github.com/repos/{REPOSITORY_INTEGRATION}/releases"
    response_mocker.add(
        url,
        mocked_response(url, status=HTTPStatus.FORBIDDEN, json_content=RATE_LIMITED),
    )
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/info",
            "repository_id": REPOSITORY_INTEGRATION_ID,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert not marketplace.system.disabled
    # Being rate limited is not the same as having no releases
    assert repository.data.releases is True


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.usefixtures("stored_repositories")
async def test_repository_remove_without_github(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test removing a downloaded repository leaves GitHub alone."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    assert repository.data.installed

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/remove",
            "repository": REPOSITORY_INTEGRATION_ID,
        }
    )
    assert (await client.receive_json())["success"]

    assert repository.data.installed is False
    assert not github_api_calls(aioclient_mock)


@pytest.mark.parametrize(
    "message",
    [pytest.param(command, id=command["type"]) for command in WARNING_COMMANDS],
)
@pytest.mark.parametrize("config_entry_source", [SOURCE_SYSTEM])
@pytest.mark.parametrize("warning_accepted", [None])
@pytest.mark.usefixtures("init_integration")
async def test_commands_need_accepted_warning(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    message: dict[str, Any],
) -> None:
    """Test the commands that download are refused until the warning is accepted."""
    client = await hass_ws_client(hass)
    calls_before = len(github_api_calls(aioclient_mock))

    await client.send_json_auto_id(message)
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == translated_error(
        "warning_not_accepted",
        "warning_not_accepted",
        "Open the Marketplace and read the warning first, downloads and updates"
        " start working once it is accepted",
    )
    assert len(github_api_calls(aioclient_mock)) == calls_before

    await client.send_json_auto_id({"type": "marketplace/warning/accept"})
    assert (await client.receive_json())["success"]

    await client.send_json_auto_id(message)
    response = await client.receive_json()

    assert response["success"]


@pytest.mark.parametrize(
    "message",
    [pytest.param(command, id=command["type"]) for command in COMMANDS_WITHOUT_WARNING],
)
@pytest.mark.parametrize("config_entry_source", [SOURCE_SYSTEM])
@pytest.mark.parametrize("warning_accepted", [None])
@pytest.mark.usefixtures("init_integration")
async def test_commands_without_accepted_warning(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    message: dict[str, Any],
) -> None:
    """Test browsing and managing the Marketplace work before the warning is accepted."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(message)
    response = await client.receive_json()

    assert response["success"]


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize("config_entry_source", [SOURCE_SYSTEM])
@pytest.mark.parametrize("warning_accepted", [None])
@pytest.mark.usefixtures("frozen_time")
async def test_accept_warning(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    init_integration: MockConfigEntry,
    marketplace: MarketplaceManager,
) -> None:
    """Test accepting the warning stores who accepted it without a reload."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "marketplace/info"})
    result = (await client.receive_json())["result"]
    assert result["warning_accepted"] is False
    assert result["warning_reminder_due"] is False

    signals: list[dict[str, Any]] = []

    @callback
    def _record_signal(data: dict[str, Any]) -> None:
        signals.append(data)

    async_dispatcher_connect(hass, MarketplaceSignal.CONFIG, _record_signal)

    await client.send_json_auto_id({"type": "marketplace/warning/accept"})
    response = await client.receive_json()
    await hass.async_block_till_done()

    assert response["success"]
    assert init_integration.data == {
        CONF_WARNING_ACCEPTED: {
            hass_admin_user.id: {"version": 1, "accepted_at": FROZEN_TIME}
        }
    }
    assert signals == [{}]

    # The same Marketplace carries on, updating the entry data does not reload it
    assert init_integration.state is ConfigEntryState.LOADED
    assert init_integration.runtime_data is marketplace

    await client.send_json_auto_id({"type": "marketplace/info"})
    result = (await client.receive_json())["result"]
    assert result["warning_accepted"] is True
    assert result["warning_reminder_due"] is False


@pytest.mark.usefixtures("init_integration")
async def test_newer_warning_needs_accepting_again(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    init_integration: MockConfigEntry,
) -> None:
    """Test an acceptance of an older warning no longer counts."""
    client = await hass_ws_client(hass)

    with patch("homeassistant.components.marketplace.base.WARNING_VERSION", 2):
        await client.send_json_auto_id({"type": "marketplace/info"})
        assert (await client.receive_json())["result"]["warning_accepted"] is False

        await client.send_json_auto_id(WARNING_COMMANDS[0])
        response = await client.receive_json()

        assert response["error"]["code"] == "warning_not_accepted"

        await client.send_json_auto_id({"type": "marketplace/warning/accept"})
        assert (await client.receive_json())["success"]

        await client.send_json_auto_id({"type": "marketplace/info"})
        assert (await client.receive_json())["result"]["warning_accepted"] is True

    assert (
        init_integration.data[CONF_WARNING_ACCEPTED][hass_admin_user.id]["version"] == 2
    )


async def test_warning_reminder(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the warning is due to be read again, without blocking anything."""
    client = await hass_ws_client(hass)
    freezer.move_to(WARNING_ACCEPTANCE["accepted_at"])

    await client.send_json_auto_id({"type": "marketplace/info"})
    assert (await client.receive_json())["result"]["warning_reminder_due"] is False

    freezer.tick(WARNING_REMINDER_INTERVAL)
    await client.send_json_auto_id({"type": "marketplace/info"})
    assert (await client.receive_json())["result"]["warning_reminder_due"] is False

    freezer.tick(timedelta(seconds=1))
    await client.send_json_auto_id({"type": "marketplace/info"})
    result = (await client.receive_json())["result"]
    assert result["warning_accepted"] is True
    assert result["warning_reminder_due"] is True

    await client.send_json_auto_id({"type": "marketplace/warning/accept"})
    assert (await client.receive_json())["success"]

    await client.send_json_auto_id({"type": "marketplace/info"})
    assert (await client.receive_json())["result"]["warning_reminder_due"] is False
    assert init_integration.data[CONF_WARNING_ACCEPTED][hass_admin_user.id] == {
        "version": 1,
        "accepted_at": dt_util.utcnow().isoformat(),
    }


@pytest.mark.parametrize(
    "message",
    [pytest.param(command, id=command["type"]) for command in WARNING_COMMANDS],
)
async def test_commands_allowed_while_reminder_due(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    init_integration: MockConfigEntry,
    message: dict[str, Any],
) -> None:
    """Test a due reminder only nudges the panel, the accepted warning still counts."""
    accepted_at = dt_util.utcnow() - WARNING_REMINDER_INTERVAL - timedelta(seconds=1)
    hass.config_entries.async_update_entry(
        init_integration,
        data={
            **init_integration.data,
            CONF_WARNING_ACCEPTED: {
                hass_admin_user.id: {
                    "version": 1,
                    "accepted_at": accepted_at.isoformat(),
                }
            },
        },
    )
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "marketplace/info"})
    assert (await client.receive_json())["result"]["warning_reminder_due"] is True

    await client.send_json_auto_id(message)
    response = await client.receive_json()

    assert response["success"]


@pytest.mark.usefixtures("init_integration")
async def test_warning_is_accepted_per_user(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    second_admin_token: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test every admin has to accept the warning, and is reminded, on their own."""
    admin_client = await hass_ws_client(hass)
    second_admin_client = await hass_ws_client(hass, second_admin_token)
    freezer.move_to(WARNING_ACCEPTANCE["accepted_at"])

    await second_admin_client.send_json_auto_id({"type": "marketplace/info"})
    assert (await second_admin_client.receive_json())["result"][
        "warning_accepted"
    ] is False

    await second_admin_client.send_json_auto_id(WARNING_COMMANDS[0])
    response = await second_admin_client.receive_json()
    assert response["error"]["code"] == "warning_not_accepted"

    await admin_client.send_json_auto_id(WARNING_COMMANDS[0])
    assert (await admin_client.receive_json())["success"]

    freezer.tick(WARNING_REMINDER_INTERVAL + timedelta(seconds=1))
    await second_admin_client.send_json_auto_id({"type": "marketplace/warning/accept"})
    assert (await second_admin_client.receive_json())["success"]

    await admin_client.send_json_auto_id({"type": "marketplace/info"})
    assert (await admin_client.receive_json())["result"]["warning_reminder_due"] is True

    await second_admin_client.send_json_auto_id({"type": "marketplace/info"})
    result = (await second_admin_client.receive_json())["result"]
    assert result["warning_accepted"] is True
    assert result["warning_reminder_due"] is False


@pytest.mark.parametrize("config_entry_source", [SOURCE_SYSTEM])
@pytest.mark.parametrize("warning_accepted", [None])
async def test_accept_warning_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    init_integration: MockConfigEntry,
) -> None:
    """Test a non admin user cannot accept the warning."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json_auto_id({"type": "marketplace/warning/accept"})
    response = await client.receive_json()

    assert response["error"]["code"] == "unauthorized"
    assert CONF_WARNING_ACCEPTED not in init_integration.data
