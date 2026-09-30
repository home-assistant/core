"""WebSocket commands for the list of repositories."""

from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.components import websocket_api
import homeassistant.helpers.config_validation as cv

from ..enums import MarketplaceSignal
from ..exceptions import AppRepositoryError, CoreRepositoryError, MarketplaceError
from ..utils import regex
from ..utils.logger import LOGGER
from .decorators import (
    marketplace_command,
    send_marketplace_error,
    send_repository_not_found,
    send_translated_error,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..base import MarketplaceManager
    from ..repositories.base import Repository


def repository_summary(
    marketplace: MarketplaceManager, repository: Repository
) -> dict[str, Any]:
    """Return what the panel shows of a repository in lists and on its page."""
    return {
        "authors": repository.data.authors,
        "available_version": repository.display_available_version,
        "can_install": repository.can_install,
        "category": repository.data.category,
        "config_flow": repository.data.config_flow,
        "custom": not marketplace.repositories.is_default(repository.data.id),
        "description": repository.data.description,
        "domain": repository.data.domain,
        "downloads": repository.data.downloads,
        "file_name": repository.data.file_name,
        "full_name": repository.data.full_name,
        "hide": repository.data.hide,
        "homeassistant": repository.repository_manifest.homeassistant,
        "id": repository.data.id,
        "installed": repository.data.installed,
        "installed_version": repository.display_installed_version,
        "last_updated": repository.data.last_updated,
        "local_path": repository.content.path.local,
        "name": repository.display_name,
        "new": repository.data.new,
        "pending_upgrade": repository.pending_update,
        "stars": repository.data.stargazers_count,
        "status": repository.display_status,
        "topics": repository.data.topics,
    }


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repositories/list",
        probatio.Optional("categories"): [str],
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repositories_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """List repositories."""
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            [
                repository_summary(marketplace, repository)
                for repository in marketplace.repositories.list_all
                if repository.data.category
                in msg.get("categories", marketplace.common.categories)
                and repository.data.last_fetched
            ],
        )
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repositories/clear_new",
        probatio.Optional("categories"): cv.ensure_list,
        probatio.Optional("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repositories_clear_new(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Clear the new flag of a repository, or of whole categories."""

    if repo := msg.get("repository"):
        if (repository := marketplace.repositories.get_by_id(repo)) is None:
            send_repository_not_found(connection, msg["id"], repo)
            return
        repository.data.new = False

    else:
        for repo in marketplace.repositories.list_all:
            if repo.data.new and repo.data.category in msg.get("categories", []):
                LOGGER.debug(
                    "Clearing new flag from '%s'",
                    repo.data.full_name,
                )
                repo.data.new = False
    marketplace.async_dispatch(MarketplaceSignal.REPOSITORY, {})
    await marketplace.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"]))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repositories/removed",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repositories_removed(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Get information about removed repositories."""
    content = [
        repo.to_json()
        for repo in marketplace.repositories.list_removed
        if repo.repository not in marketplace.common.ignored_repositories
    ]
    connection.send_message(websocket_api.result_message(msg["id"], content))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repositories/add",
        probatio.Required("repository"): cv.string,
        probatio.Required("category"): probatio.Lower,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command(requires_accepted_warning=True, requires_github=True)
async def marketplace_repositories_add(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Add a custom repository."""
    repository = regex.extract_repository_from_url(msg["repository"])
    category = msg["category"]

    if repository is None:
        send_translated_error(
            connection,
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            "invalid_repository",
            {"repository": msg["repository"]},
        )
        return

    if category not in marketplace.common.categories:
        send_translated_error(
            connection,
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            "invalid_category",
            {"category": category},
        )
        return

    if repository in marketplace.common.skip:
        marketplace.common.skip.remove(repository)

    if renamed := marketplace.common.renamed_repositories.get(repository):
        repository = renamed

    if marketplace.repositories.get_by_full_name(repository):
        send_translated_error(
            connection,
            msg["id"],
            "repository_exists",
            "repository_exists",
            {"repository": repository},
        )
        return

    try:
        errors = await marketplace.async_register_repository(
            repository_full_name=repository,
            category=category,
        )
    except CoreRepositoryError:
        send_translated_error(
            connection, msg["id"], "core_repository", "core_repository"
        )
        return
    except AppRepositoryError:
        send_translated_error(
            connection,
            msg["id"],
            "app_repository",
            "app_repository",
            {"repository": repository},
        )
        return
    except MarketplaceError as exception:
        send_marketplace_error(
            connection,
            msg["id"],
            "add_failed",
            exception,
            "add_failed",
            {"repository": repository},
        )
        return

    # All of them are in the log already, the first tells what to fix
    if errors:
        send_marketplace_error(
            connection,
            msg["id"],
            "add_failed",
            errors[0],
            "add_failed",
            {"repository": repository},
        )
        return

    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repositories/remove",
        probatio.Required("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repositories_remove(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Remove a custom repository from the list."""
    repository = marketplace.repositories.get_by_id(msg["repository"])
    if repository is None:
        send_repository_not_found(connection, msg["id"], msg["repository"])
        return

    # Forgetting it would leave its files running, without updates
    if repository.data.installed:
        send_translated_error(
            connection,
            msg["id"],
            "repository_installed",
            "repository_installed",
            {"repository": repository.data.full_name},
        )
        return

    repository.remove()
    marketplace.common.custom_repositories.discard(repository.data.id)
    await marketplace.data.async_write()

    connection.send_message(websocket_api.result_message(msg["id"], {}))
