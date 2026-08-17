"""Tests for the Portainer update platform."""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
)
from pyportainer.models.docker import LocalImageInformation
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.portainer.const import CONF_GITHUB_TOKEN, DOMAIN
from homeassistant.components.portainer.update import (
    RELEASE_NOTES_CACHE_TTL,
    _fetch_ghcr_release_notes,
    _fetch_linuxserver_release_notes,
    _format_version,
    _image_attributes,
    _release_url,
    _short_digest,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, load_json_value_fixture, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator

ENTITY_ID = "update.funny_chatelet_image_update_available"


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("mock_portainer_client")
async def test_update_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test for all Portainer update entities."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass,
            entity_registry,
            snapshot,
            mock_config_entry.entry_id,
        )


async def test_update_install(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful container image update installation."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    mock_portainer_client.container_recreate.assert_called_once()


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (PortainerAuthenticationError("auth"), "invalid_auth_no_details"),
        (PortainerConnectionError("conn"), "cannot_connect_no_details"),
    ],
)
async def test_update_install_errors(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test container image update install error handling."""
    mock_portainer_client.container_recreate.side_effect = exception

    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )


async def test_update_using_cache(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the update entity uses the cache and doesn't call the API."""
    mock_portainer_watcher.last_check = 1234

    with (
        patch(
            "homeassistant.components.portainer.coordinator.time.monotonic",
            return_value=1235.0,
        ),
        patch(
            "homeassistant.components.portainer._PLATFORMS",
            [Platform.UPDATE],
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    # Reset call counts, since it needs to be measured what happens in this sequence
    mock_portainer_client.get_image.reset_mock()

    # Trigger a refresh, but it should use the cache
    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    mock_portainer_client.get_image.assert_not_called()


@pytest.mark.parametrize(
    ("digest", "expected"),
    [
        pytest.param(None, None, id="none"),
        pytest.param(
            "sha256:afcc7f1ac1b49db317a7196c902e61c6c3c4607d63599ee1a82d702d249a0ccb",
            "sha256:afcc7f1ac1b4",
            id="full_digest",
        ),
        pytest.param(
            "example@sha256:afcc7f1ac1b49db317a7196c902e61c6c3c4607d63599ee1a82d702d249a0ccb",
            "sha256:afcc7f1ac1b4",
            id="repo_prefix",
        ),
    ],
)
def test_short_digest(digest: str | None, expected: str | None) -> None:
    """Test _short_digest produces a 12-character Docker-style short form."""
    assert _short_digest(digest) == expected


@pytest.mark.parametrize(
    ("digest", "image", "expected"),
    [
        pytest.param(None, None, None, id="no_digest"),
        pytest.param(
            "sha256:afcc7f1ac1b49db317a7196c902e61c6c3c4607d63599ee1a82d702d249a0ccb",
            None,
            "sha256:afcc7f1ac1b4",
            id="no_image",
        ),
        pytest.param(
            "sha256:afcc7f1ac1b49db317a7196c902e61c6c3c4607d63599ee1a82d702d249a0ccb",
            "app:latest",
            "app:latest (sha256:afcc7f1ac1b4)",
            id="with_image",
        ),
    ],
)
def test_format_version(
    digest: str | None, image: str | None, expected: str | None
) -> None:
    """Test _format_version combines the image reference and short digest."""
    assert _format_version(digest, image) == expected


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        pytest.param(None, None, id="none"),
        pytest.param(
            "ubuntu:latest",
            "https://hub.docker.com/r/ubuntu/tags?name=latest",
            id="docker_hub_bare_name",
        ),
        pytest.param(
            "ubuntu",
            "https://hub.docker.com/r/ubuntu/tags?name=latest",
            id="docker_hub_bare_no_tag",
        ),
        pytest.param(
            "docker.io/library/ubuntu:latest",
            "https://hub.docker.com/_/ubuntu/tags?name=latest",
            id="docker_io_library",
        ),
        pytest.param(
            "docker.io/lissy93/dashy:latest",
            "https://hub.docker.com/r/lissy93/dashy/tags?name=latest",
            id="docker_io_user",
        ),
        pytest.param(
            "ghcr.io/owner/myapp:v1.0",
            "https://github.com/owner/myapp/pkgs/container/myapp",
            id="ghcr_io",
        ),
        pytest.param(
            "lscr.io/linuxserver/sonarr:latest",
            "https://docs.linuxserver.io/images/docker-sonarr/#versions",
            id="linuxserver",
        ),
        pytest.param(
            "lscr.io/linuxserver/sonarr",
            "https://docs.linuxserver.io/images/docker-sonarr/#versions",
            id="linuxserver_no_tag",
        ),
        pytest.param(
            "lscr.io/other/sonarr:latest",
            None,
            id="lscr_io_non_linuxserver_namespace",
        ),
        pytest.param(
            "lscr.io/linuxserver/sonarr/extra:latest",
            None,
            id="linuxserver_nested",
        ),
        pytest.param(
            "ghcr.io/org/sub/app:latest",
            None,
            id="ghcr_io_nested",
        ),
        pytest.param(
            "quay.io/prometheus/prometheus:latest",
            None,
            id="unknown_registry",
        ),
        pytest.param(
            "internal.registry.example.com:5000/example:1.0",
            None,
            id="private_registry_with_port",
        ),
        pytest.param(
            "localhost:5000/myimage:1.0",
            None,
            id="localhost_registry_with_port",
        ),
        pytest.param(
            "registry:5000/myimage",
            None,
            id="dotless_registry_with_port",
        ),
    ],
)
def test_release_url(image: str | None, expected: str | None) -> None:
    """Test _release_url returns tag page links for known registries only."""
    assert _release_url(image) == expected


@pytest.mark.parametrize(
    ("size", "created", "expected"),
    [
        pytest.param(None, None, {}, id="no_size_no_created"),
        pytest.param(1239828, None, {"image_size": 1239828}, id="size_only"),
        pytest.param(
            None,
            "2022-02-04T21:20:12.497794809Z",
            {"image_created": datetime(2022, 2, 4, 21, 20, 12, 497794, tzinfo=UTC)},
            id="created_only",
        ),
        pytest.param(None, "not-a-date", {}, id="unparsable_created"),
        pytest.param(None, "", {}, id="empty_created"),
        pytest.param(
            1239828,
            "2022-02-04T21:20:12.497794809Z",
            {
                "image_size": 1239828,
                "image_created": datetime(2022, 2, 4, 21, 20, 12, 497794, tzinfo=UTC),
            },
            id="size_and_created",
        ),
    ],
)
def test_image_attributes(
    size: int | None, created: str | None, expected: dict[str, object]
) -> None:
    """Test _image_attributes omits missing or unparsable fields."""
    local_image = LocalImageInformation.from_dict(
        load_json_value_fixture("local_image_information.json", DOMAIN)
        | {"Size": size, "Created": created}
    )
    assert _image_attributes(local_image) == expected


async def test_fetch_ghcr_release_notes(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test _fetch_ghcr_release_notes returns the latest GitHub release body."""
    aioclient_mock.get(
        "https://api.github.com/repos/owner/myapp/releases/latest",
        json={"body": "## What's new\n- Fixed a bug"},
    )
    assert (
        await _fetch_ghcr_release_notes(hass, "owner", "myapp", None)
        == "## What's new\n- Fixed a bug"
    )


async def test_fetch_ghcr_release_notes_no_release(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test _fetch_ghcr_release_notes returns None when there is no release."""
    aioclient_mock.get(
        "https://api.github.com/repos/owner/myapp/releases/latest",
        status=HTTPStatus.NOT_FOUND,
    )
    assert await _fetch_ghcr_release_notes(hass, "owner", "myapp", None) is None


async def test_fetch_ghcr_release_notes_empty_body(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test _fetch_ghcr_release_notes returns None when the release has no body."""
    aioclient_mock.get(
        "https://api.github.com/repos/owner/myapp/releases/latest",
        json={"body": None},
    )
    assert await _fetch_ghcr_release_notes(hass, "owner", "myapp", None) is None


async def test_fetch_ghcr_release_notes_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test _fetch_ghcr_release_notes returns None on a connection error."""
    aioclient_mock.get(
        "https://api.github.com/repos/owner/myapp/releases/latest",
        exc=ClientConnectionError,
    )
    assert await _fetch_ghcr_release_notes(hass, "owner", "myapp", None) is None


async def test_fetch_ghcr_release_notes_with_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test _fetch_ghcr_release_notes sends an Authorization header when given a token."""
    aioclient_mock.get(
        "https://api.github.com/repos/owner/myapp/releases/latest",
        json={"body": "Release notes"},
    )
    assert (
        await _fetch_ghcr_release_notes(hass, "owner", "myapp", "ghp_secret")
        == "Release notes"
    )
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer ghp_secret"


async def test_fetch_ghcr_release_notes_without_token_no_auth_header(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test _fetch_ghcr_release_notes omits the Authorization header without a token."""
    aioclient_mock.get(
        "https://api.github.com/repos/owner/myapp/releases/latest",
        json={"body": "Release notes"},
    )
    await _fetch_ghcr_release_notes(hass, "owner", "myapp", None)
    assert "Authorization" not in aioclient_mock.mock_calls[0][3]


async def test_fetch_linuxserver_release_notes(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test _fetch_linuxserver_release_notes formats the most recent changelog entries."""
    aioclient_mock.get(
        "https://raw.githubusercontent.com/linuxserver/docker-sonarr"
        "/master/readme-vars.yml",
        text="changelogs:\n"
        '  - {date: "09.07.26", desc: "Workaround malformed ncurses database."}\n'
        '  - {date: "04.07.26", desc: "Rebase to Alpine 3.24."}\n',
    )
    assert await _fetch_linuxserver_release_notes(hass, "sonarr", None) == (
        "**09.07.26** Workaround malformed ncurses database.\n\n"
        "**04.07.26** Rebase to Alpine 3.24."
    )


async def test_fetch_linuxserver_release_notes_with_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test _fetch_linuxserver_release_notes sends an Authorization header with a token."""
    aioclient_mock.get(
        "https://raw.githubusercontent.com/linuxserver/docker-sonarr"
        "/master/readme-vars.yml",
        text='changelogs:\n  - {date: "09.07.26", desc: "Some change."}\n',
    )
    await _fetch_linuxserver_release_notes(hass, "sonarr", "ghp_secret")
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer ghp_secret"


async def test_fetch_linuxserver_release_notes_caps_entries(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test _fetch_linuxserver_release_notes caps the number of returned entries."""
    changelogs = "\n".join(
        f'  - {{date: "{i:02}.01.20", desc: "Change {i}."}}' for i in range(1, 20)
    )
    aioclient_mock.get(
        "https://raw.githubusercontent.com/linuxserver/docker-sonarr"
        "/master/readme-vars.yml",
        text=f"changelogs:\n{changelogs}\n",
    )
    notes = await _fetch_linuxserver_release_notes(hass, "sonarr", None)
    assert notes is not None
    assert notes.count("\n\n") == 9  # 10 entries joined by 9 blank lines


@pytest.mark.parametrize(
    "yaml_body",
    [
        pytest.param("not: valid: yaml: :", id="malformed_yaml"),
        pytest.param("some_other_key: value\n", id="missing_changelogs"),
        pytest.param("changelogs: not_a_list\n", id="changelogs_not_a_list"),
        pytest.param("changelogs: []\n", id="empty_changelogs"),
        pytest.param(
            'changelogs:\n  - {desc: "Missing date"}\n', id="entry_missing_date"
        ),
    ],
)
async def test_fetch_linuxserver_release_notes_invalid(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, yaml_body: str
) -> None:
    """Test _fetch_linuxserver_release_notes returns None for unusable content."""
    aioclient_mock.get(
        "https://raw.githubusercontent.com/linuxserver/docker-sonarr"
        "/master/readme-vars.yml",
        text=yaml_body,
    )
    assert await _fetch_linuxserver_release_notes(hass, "sonarr", None) is None


async def test_async_release_notes_unrecognized_registry(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test release notes are None for a registry release_url doesn't recognize."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "update/release_notes", "entity_id": ENTITY_ID}
    )
    result = await client.receive_json()

    assert result["result"] is None
    assert aioclient_mock.call_count == 0


async def test_async_release_notes_linuxserver(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test release notes are fetched for a recognized lscr.io/linuxserver image."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    coordinator.data[1].containers[
        "funny_chatelet"
    ].container.image = "lscr.io/linuxserver/sonarr:latest"
    aioclient_mock.get(
        "https://raw.githubusercontent.com/linuxserver/docker-sonarr"
        "/master/readme-vars.yml",
        text='changelogs:\n  - {date: "09.07.26", desc: "Some change."}\n',
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "update/release_notes", "entity_id": ENTITY_ID}
    )
    result = await client.receive_json()

    assert result["result"] == "**09.07.26** Some change."


async def test_async_release_notes_uses_configured_github_token(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a configured GitHub token is sent as an Authorization header."""
    config_entry = MockConfigEntry(
        domain=mock_config_entry.domain,
        title=mock_config_entry.title,
        data={**mock_config_entry.data, CONF_GITHUB_TOKEN: "ghp_secret"},
        unique_id=mock_config_entry.unique_id,
        entry_id=mock_config_entry.entry_id,
        version=mock_config_entry.version,
    )
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, config_entry)

    coordinator = config_entry.runtime_data
    coordinator.data[1].containers[
        "funny_chatelet"
    ].container.image = "ghcr.io/owner/myapp:latest"
    aioclient_mock.get(
        "https://api.github.com/repos/owner/myapp/releases/latest",
        json={"body": "Release notes"},
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "update/release_notes", "entity_id": ENTITY_ID}
    )
    result = await client.receive_json()

    assert result["result"] == "Release notes"
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer ghp_secret"


async def test_async_release_notes_cached(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test release notes are cached and not re-fetched on the same image."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    coordinator.data[1].containers[
        "funny_chatelet"
    ].container.image = "lscr.io/linuxserver/sonarr:latest"
    aioclient_mock.get(
        "https://raw.githubusercontent.com/linuxserver/docker-sonarr"
        "/master/readme-vars.yml",
        text='changelogs:\n  - {date: "09.07.26", desc: "Some change."}\n',
    )

    client = await hass_ws_client(hass)
    for msg_id in (1, 2):
        await client.send_json(
            {"id": msg_id, "type": "update/release_notes", "entity_id": ENTITY_ID}
        )
        result = await client.receive_json()
        assert result["result"] == "**09.07.26** Some change."

    assert aioclient_mock.call_count == 1


async def test_async_release_notes_cache_expires(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test release notes are re-fetched once the cache expires."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    coordinator.data[1].containers[
        "funny_chatelet"
    ].container.image = "lscr.io/linuxserver/sonarr:latest"
    aioclient_mock.get(
        "https://raw.githubusercontent.com/linuxserver/docker-sonarr"
        "/master/readme-vars.yml",
        text='changelogs:\n  - {date: "09.07.26", desc: "Some change."}\n',
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "update/release_notes", "entity_id": ENTITY_ID}
    )
    await client.receive_json()

    freezer.tick(RELEASE_NOTES_CACHE_TTL + timedelta(minutes=1))

    await client.send_json(
        {"id": 2, "type": "update/release_notes", "entity_id": ENTITY_ID}
    )
    await client.receive_json()

    assert aioclient_mock.call_count == 2
