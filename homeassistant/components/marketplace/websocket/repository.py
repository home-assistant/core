"""Register info websocket commands."""

from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.components import websocket_api
import homeassistant.helpers.config_validation as cv

from ..enums import MarketplaceSignal, RepositoryCategory
from ..exceptions import (
    GitHubAnonymousRateLimitError,
    GitHubRateLimitError,
    MarketplaceError,
    ReplacesBuiltInNotConfirmedError,
)
from ..utils.logger import LOGGER
from ..utils.version import version_left_higher_then_right
from .decorators import (
    ERR_GITHUB_RATE_LIMITED,
    marketplace_command,
    send_repository_not_found,
    send_translated_error,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..base import MarketplaceManager


def _send_rate_limited(
    connection: websocket_api.ActiveConnection,
    msg_id: int,
    exception: GitHubRateLimitError,
) -> None:
    """Answer that GitHub refused the request, the rate limit ran out."""
    send_translated_error(connection, msg_id, ERR_GITHUB_RATE_LIMITED, "rate_limited")


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/info",
        probatio.Required("repository_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repository_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Return information about a repository."""
    repository_id = msg["repository_id"]
    repository = marketplace.repositories.get_by_id(repository_id)
    if repository is None:
        send_repository_not_found(connection, msg["id"], repository_id)
        return

    if not repository.updated_info:
        try:
            await repository.update_repository(ignore_issues=True, force=True)
        except GitHubAnonymousRateLimitError:
            # Show what is known, the next visit tries again
            repository.logger.debug("%s Rate limited", repository.string)
        except MarketplaceError as exception:
            repository.logger.error("%s %s", repository.string, exception)
            repository.updated_info = True
        else:
            repository.updated_info = True

    if repository.data.new:
        repository.data.new = False
        await marketplace.data.async_write()

    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            {
                "additional_info": repository.additional_info,
                "authors": repository.data.authors,
                "available_version": repository.display_available_version,
                "beta": repository.data.show_beta,
                "can_download": repository.can_download,
                "category": repository.data.category,
                "config_flow": repository.data.config_flow,
                "custom": not marketplace.repositories.is_default(
                    str(repository.data.id)
                ),
                "default_branch": repository.data.default_branch,
                "description": repository.data.description,
                "domain": repository.data.domain,
                "downloads": repository.data.downloads,
                "file_name": repository.data.file_name,
                "full_name": repository.data.full_name,
                "hide_default_branch": repository.repository_manifest.hide_default_branch,
                "homeassistant": repository.repository_manifest.homeassistant,
                "id": repository.data.id,
                "installed_version": repository.display_installed_version,
                "installed": repository.data.installed,
                "issues": repository.data.open_issues,
                "last_updated": repository.data.last_updated,
                "local_path": repository.content.path.local,
                "name": repository.display_name,
                "new": False,
                "pending_upgrade": repository.pending_update,
                "releases": repository.data.published_tags,
                "ref": repository.ref,
                "replaces_built_in": await repository.async_replaces_built_in(),
                "selected_tag": repository.data.selected_tag,
                "stars": repository.data.stargazers_count,
                "state": repository.state,
                "status": repository.display_status,
                "topics": repository.data.topics,
                "version_or_commit": repository.display_version_or_commit,
            },
        )
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/ignore",
        probatio.Required("repository"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repository_ignore(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Ignore a repository."""
    repository_id = msg["repository"]
    LOGGER.info("Ignoring %s", repository_id)
    repository = marketplace.repositories.get_by_id(repository_id)
    if repository is None:
        send_repository_not_found(connection, msg["id"], repository_id)
        return

    marketplace.common.ignored_repositories.add(repository.data.full_name)

    await marketplace.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"]))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/state",
        probatio.Required("repository"): cv.string,
        probatio.Required("state"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repository_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Set the state of a repository."""
    repository = marketplace.repositories.get_by_id(msg["repository"])
    if repository is None:
        send_repository_not_found(connection, msg["id"], msg["repository"])
        return

    repository.state = msg["state"]

    await marketplace.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/version",
        probatio.Required("repository"): cv.string,
        probatio.Required("version"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command(requires_accepted_warning=True)
async def marketplace_repository_version(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Set the version of a repository."""
    repository = marketplace.repositories.get_by_id(msg["repository"])
    if repository is None:
        send_repository_not_found(connection, msg["id"], msg["repository"])
        return

    selected_tag = repository.data.selected_tag
    if msg["version"] == repository.data.default_branch:
        repository.data.selected_tag = None
    else:
        repository.data.selected_tag = msg["version"]

    try:
        await repository.update_repository(force=True)
    except GitHubAnonymousRateLimitError as exception:
        repository.data.selected_tag = selected_tag
        _send_rate_limited(connection, msg["id"], exception)
        return
    repository.state = None

    await marketplace.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/beta",
        probatio.Required("repository"): cv.string,
        probatio.Required("show_beta"): cv.boolean,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command(requires_accepted_warning=True)
async def marketplace_repository_beta(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Show or hide beta versions of a repository."""
    repository = marketplace.repositories.get_by_id(msg["repository"])
    if repository is None:
        send_repository_not_found(connection, msg["id"], msg["repository"])
        return

    show_beta = repository.data.show_beta
    repository.data.show_beta = msg["show_beta"]

    try:
        await repository.update_repository(force=True)
    except GitHubAnonymousRateLimitError as exception:
        repository.data.show_beta = show_beta
        _send_rate_limited(connection, msg["id"], exception)
        return
    repository.state = None

    await marketplace.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/download",
        probatio.Required("repository"): cv.string,
        probatio.Optional("version"): cv.string,
        probatio.Optional("confirm_replace_built_in", default=False): cv.boolean,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command(requires_accepted_warning=True)
async def marketplace_repository_download(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Download a repository, or another version of it."""
    repository = marketplace.repositories.get_by_id(msg["repository"])
    if repository is None:
        send_repository_not_found(connection, msg["id"], msg["repository"])
        return

    try:
        was_installed = repository.data.installed
        await repository.async_download_repository(
            ref=msg.get("version"),
            confirm_replace_built_in=msg["confirm_replace_built_in"],
        )
        if not was_installed:
            marketplace.async_dispatch(MarketplaceSignal.RELOAD, {"force": True})
            await marketplace.async_recreate_entities()

        await marketplace.data.async_write()
        connection.send_message(websocket_api.result_message(msg["id"], {}))
    except GitHubAnonymousRateLimitError as exception:
        _send_rate_limited(connection, msg["id"], exception)
    except ReplacesBuiltInNotConfirmedError as exception:
        # Confirmed with the first download, updates replace the same integration
        send_translated_error(
            connection,
            msg["id"],
            "replaces_built_in",
            "replaces_built_in_not_confirmed",
            {"repository": repository.data.full_name, "domain": exception.domain},
        )
    except MarketplaceError as exception:
        repository.logger.error("%s %s", repository.string, exception)
        send_translated_error(
            connection,
            msg["id"],
            "error",
            "download_failed",
            {"repository": repository.data.full_name, "error": str(exception)},
        )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/remove",
        probatio.Required("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repository_remove(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Remove a repository."""
    repository = marketplace.repositories.get_by_id(msg["repository"])
    if repository is None:
        send_repository_not_found(connection, msg["id"], msg["repository"])
        return

    repository.data.new = False
    # What is on disk is enough to remove it, GitHub is only asked when it can be,
    # or for a theme that was stored before its file name was
    theme_without_file_name = (
        repository.data.category == RepositoryCategory.THEME
        and not repository.data.file_name
    )
    if marketplace.github_connected or theme_without_file_name:
        try:
            await repository.update_repository(ignore_issues=True, force=True)
        except MarketplaceError as exception:
            repository.logger.error("%s %s", repository.string, exception)

    try:
        await repository.uninstall()
    except MarketplaceError:
        send_translated_error(
            connection,
            msg["id"],
            "remove_failed",
            "remove_failed",
            {"repository": repository.data.full_name},
        )
        return

    await marketplace.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/refresh",
        probatio.Required("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repository_refresh(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Refresh a repository."""
    repository = marketplace.repositories.get_by_id(msg["repository"])
    if repository is None:
        send_repository_not_found(connection, msg["id"], msg["repository"])
        return

    try:
        await repository.update_repository(ignore_issues=True, force=True)
    except GitHubAnonymousRateLimitError as exception:
        _send_rate_limited(connection, msg["id"], exception)
        return

    await marketplace.data.async_write()
    # Update state of update entity
    marketplace.coordinators[repository.data.category].async_update_listeners()

    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/release_notes",
        probatio.Required("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repository_release_notes(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Return release notes."""
    repository = marketplace.repositories.get_by_id(msg["repository"])
    if repository is None:
        send_repository_not_found(connection, msg["id"], msg["repository"])
        return

    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            [
                {
                    "name": x.name,
                    "body": x.body,
                    "tag": x.tag_name,
                }
                for x in repository.releases.objects
                if not repository.data.installed_version
                or version_left_higher_then_right(
                    x.tag_name, repository.data.installed_version
                )
            ],
        )
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/releases",
        probatio.Required("repository_id"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repository_releases(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Return releases."""
    repository = marketplace.repositories.get_by_id(msg["repository_id"])
    if repository is None:
        send_repository_not_found(connection, msg["id"], msg["repository_id"])
        return

    try:
        releases = await repository.async_get_releases()
    except GitHubRateLimitError as exception:
        _send_rate_limited(connection, msg["id"], exception)
        return
    except MarketplaceError as exception:
        LOGGER.exception("Could not get the releases for %s", repository.string)
        send_translated_error(
            connection,
            msg["id"],
            "unknown",
            "releases_failed",
            {"repository": repository.data.full_name, "error": str(exception)},
        )
        return

    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            [
                {
                    "name": release.name,
                    "tag": release.tag_name,
                    "published_at": release.published_at,
                    "prerelease": release.prerelease,
                }
                for release in releases
            ],
        )
    )
