"""Register info websocket commands."""

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import websocket_api
import homeassistant.helpers.config_validation as cv

from ..base import async_get_store
from ..enums import StoreSignal
from ..exceptions import StoreError
from ..utils import regex
from ..utils.logger import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@websocket_api.websocket_command(
    {
        vol.Required("type"): "marketplace/repositories/list",
        vol.Optional("categories"): [str],
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def store_repositories_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List repositories."""
    store = async_get_store(hass)
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            [
                {
                    "authors": repo.data.authors,
                    "available_version": repo.display_available_version,
                    "installed_version": repo.display_installed_version,
                    "config_flow": repo.data.config_flow,
                    "can_download": repo.can_download,
                    "category": repo.data.category,
                    "country": repo.repository_manifest.country,
                    "custom": not store.repositories.is_default(str(repo.data.id)),
                    "description": repo.data.description,
                    "domain": repo.data.domain,
                    "downloads": repo.data.downloads,
                    "file_name": repo.data.file_name,
                    "full_name": repo.data.full_name,
                    "hide": repo.data.hide,
                    "homeassistant": repo.repository_manifest.homeassistant,
                    "id": repo.data.id,
                    "installed": repo.data.installed,
                    "last_updated": repo.data.last_updated,
                    "local_path": repo.content.path.local,
                    "name": repo.display_name,
                    "new": repo.data.new,
                    "pending_upgrade": repo.pending_update,
                    "stars": repo.data.stargazers_count,
                    "state": repo.state,
                    "status": repo.display_status,
                    "topics": repo.data.topics,
                }
                for repo in store.repositories.list_all
                if repo.data.category in msg.get("categories", store.common.categories)
                and not repo.ignored_by_country_configuration
                and repo.data.last_fetched
            ],
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "marketplace/repositories/clear_new",
        vol.Optional("categories"): cv.ensure_list,
        vol.Optional("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def store_repositories_clear_new(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Clear new repositories for specific categories."""
    store = async_get_store(hass)

    if repo := msg.get("repository"):
        if (repository := store.repositories.get_by_id(repo)) is None:
            connection.send_error(
                msg["id"],
                "repository_not_found",
                f"Repository with ID ({repo}) not found",
            )
            return
        repository.data.new = False

    else:
        for repo in store.repositories.list_all:
            if repo.data.new and repo.data.category in msg.get("categories", []):
                LOGGER.debug(
                    "Clearing new flag from '%s'",
                    repo.data.full_name,
                )
                repo.data.new = False
    store.async_dispatch(StoreSignal.REPOSITORY, {})
    await store.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "marketplace/repositories/removed",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def store_repositories_removed(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get information about removed repositories."""
    store = async_get_store(hass)
    content = [
        repo.to_json()
        for repo in store.repositories.list_removed
        if repo.repository not in store.common.ignored_repositories
    ]
    connection.send_message(websocket_api.result_message(msg["id"], content))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "marketplace/repositories/add",
        vol.Required("repository"): cv.string,
        vol.Required("category"): vol.Lower,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def store_repositories_add(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Add custom repositoriy."""
    store = async_get_store(hass)
    repository = regex.extract_repository_from_url(msg["repository"])
    category = msg["category"]

    if repository is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            f"Could not read a repository from '{msg['repository']}'",
        )
        return

    if repository in store.common.skip:
        store.common.skip.remove(repository)

    if renamed := store.common.renamed_repositories.get(repository):
        repository = renamed

    if category not in store.common.categories:
        LOGGER.error("%s is not a valid category for %s", category, repository)

    elif not store.repositories.get_by_full_name(repository):
        try:
            await store.async_register_repository(
                repository_full_name=repository,
                category=category,
            )

        except StoreError as exception:
            store.async_dispatch(
                StoreSignal.ERROR,
                {
                    "action": "add_repository",
                    "exception": type(exception).__name__,
                    "message": str(exception),
                },
            )

    else:
        store.async_dispatch(
            StoreSignal.ERROR,
            {
                "action": "add_repository",
                "message": f"Repository '{repository}' exists in the Marketplace.",
            },
        )

    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "marketplace/repositories/remove",
        vol.Required("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def store_repositories_remove(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Remove custom repositoriy."""
    store = async_get_store(hass)
    repository = store.repositories.get_by_id(msg["repository"])
    if repository is None:
        connection.send_error(
            msg["id"],
            "repository_not_found",
            f"Repository with ID ({msg['repository']}) not found",
        )
        return

    repository.remove()
    await store.data.async_write()

    connection.send_message(websocket_api.result_message(msg["id"], {}))
