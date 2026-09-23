"""Tests for the Marketplace WebSocket API."""

from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.marketplace.base import StoreManager
from homeassistant.components.marketplace.const import DOMAIN
from homeassistant.components.marketplace.enums import RepositoryCategory, StoreSignal
from homeassistant.components.marketplace.exceptions import StoreError
from homeassistant.components.marketplace.utils.storage import async_save_to_storage
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import REPOSITORY_INTEGRATION, REPOSITORY_INTEGRATION_ID

from tests.common import MockConfigEntry
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
    {"type": "marketplace/subscribe", "signal": StoreSignal.REPOSITORY},
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
    assert response["error"] == {
        "code": "repository_not_found",
        "message": "Repository with ID (0) not found",
    }


@pytest.mark.usefixtures("init_integration")
async def test_info(hass: HomeAssistant, hass_ws_client: WebSocketGenerator) -> None:
    """Test the information about the Marketplace itself."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "marketplace/info"})
    response = await client.receive_json()

    assert response["success"]
    # The categories are a set, so they are asserted separately in their own test
    assert response["result"] | {"categories": None} == {
        "categories": None,
        "country": "ALL",
        "debug": False,
        "disabled_reason": None,
        "has_pending_tasks": False,
        "lovelace_mode": "storage",
        "stage": "running",
        "startup": False,
        "version": HA_VERSION,
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
    assert response["error"]["code"] == "home_assistant_error"


@pytest.mark.usefixtures("init_integration")
async def test_subscribe(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that a subscription forwards the Marketplace events."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "marketplace/subscribe", "signal": StoreSignal.REPOSITORY}
    )
    assert (await client.receive_json())["success"]

    async_dispatcher_send(
        hass, StoreSignal.REPOSITORY, {"action": "update", "id": 1337}
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


async def test_repository_info_clears_new(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that looking at a repository stops it from being new."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
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
    store: StoreManager,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a repository that can not be refreshed still reports back."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    client = await hass_ws_client(hass)
    with patch.object(repository, "update_repository", side_effect=StoreError("Nope")):
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
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing every known repository."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "marketplace/repositories/list"})
    response = await client.receive_json()

    assert response["success"]
    assert {repository["full_name"] for repository in response["result"]} == {
        repository.data.full_name for repository in store.repositories.list_all
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


async def test_repositories_list_skips_other_countries(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that a repository for another country is not listed."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.repository_manifest.country = ["NO"]
    store.configuration.country = "SE"

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "marketplace/repositories/list"})
    response = await client.receive_json()

    assert response["success"]
    assert REPOSITORY_INTEGRATION not in [
        repository["full_name"] for repository in response["result"]
    ]


async def test_repositories_removed(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing the repositories that were removed from the Marketplace."""
    removed = store.repositories.removed_repository("removed/repository")
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
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that an ignored repository is not reported as removed."""
    store.repositories.removed_repository("removed/repository")
    store.common.ignored_repositories.add("removed/repository")

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "marketplace/repositories/removed"})
    response = await client.receive_json()

    assert response["success"]
    assert "removed/repository" not in [
        entry["repository"] for entry in response["result"]
    ]


async def test_repositories_clear_new_for_categories(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test clearing the new flag of a whole category."""
    integration = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    plugin = store.repositories.get_by_full_name("hacs-test-org/plugin-basic")
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
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test clearing the new flag of a single repository."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
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


async def test_repositories_add_existing(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test adding a repository the Marketplace already knows."""
    client = await hass_ws_client(hass)
    with patch.object(store, "async_dispatch", side_effect=None) as dispatch:
        await client.send_json_auto_id(
            {
                "type": "marketplace/repositories/add",
                "repository": REPOSITORY_INTEGRATION,
                "category": "integration",
            }
        )
        assert (await client.receive_json())["success"]

    assert [call.args[1] for call in dispatch.call_args_list] == [
        {
            "action": "add_repository",
            "message": f"Repository '{REPOSITORY_INTEGRATION}' exists in the Marketplace.",
        }
    ]


@pytest.mark.usefixtures("init_integration")
async def test_repositories_add_unknown_category(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test adding a repository to a category that is not active."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "marketplace/repositories/add",
            "repository": "test/test",
            "category": "netdaemon",
        }
    )
    assert (await client.receive_json())["success"]

    assert "netdaemon is not a valid category for test/test" in caplog.text


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
    assert response["error"] == {
        "code": "invalid_format",
        "message": "Could not read a repository from 'https://example.com/'",
    }


async def test_repositories_remove(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
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

    assert store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID) is None


async def test_repository_ignore(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
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

    assert REPOSITORY_INTEGRATION in store.common.ignored_repositories


async def test_repository_state(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
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

    assert store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID).state == "other"


async def test_repository_version(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test pinning a repository to a version."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

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
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that selecting the default branch stops pinning the repository."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
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
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
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

    assert store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID).data.show_beta


async def test_repository_refresh(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test refreshing a single repository."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

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
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
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

    assert store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID).data.installed


async def test_repository_download_failure(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a download that can not be completed."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    client = await hass_ws_client(hass)
    with patch.object(
        repository,
        "async_download_repository",
        side_effect=StoreError("Could not download"),
    ):
        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/download",
                "repository": REPOSITORY_INTEGRATION_ID,
            }
        )
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == {"code": "error", "message": "Could not download"}


async def test_repository_remove(
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing a downloaded repository."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

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
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the release notes of the versions newer than the downloaded one."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
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
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that a repository that is not downloaded lists every release."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
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
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
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
    hass: HomeAssistant, store: StoreManager, hass_ws_client: WebSocketGenerator
) -> None:
    """Test releases that can not be fetched."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    client = await hass_ws_client(hass)
    with patch.object(
        repository, "async_get_releases", side_effect=StoreError("Rate limited")
    ):
        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/releases",
                "repository_id": REPOSITORY_INTEGRATION_ID,
            }
        )
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == {"code": "unknown", "message": "Rate limited"}


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
        RepositoryCategory.APPDAEMON,
        RepositoryCategory.INTEGRATION,
        RepositoryCategory.PLUGIN,
        RepositoryCategory.TEMPLATE,
        RepositoryCategory.THEME,
    }
