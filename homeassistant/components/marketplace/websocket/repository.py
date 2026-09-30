"""WebSocket commands for a single repository."""

from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.components import websocket_api
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import SIGNAL_REPOSITORY_INSTALLED
from ..enums import RepositoryCategory
from ..exceptions import (
    GitHubAnonymousRateLimitError,
    GitHubRateLimitError,
    MarketplaceError,
    ReplacesBuiltInNotConfirmedError,
    RepositoryBusyError,
)
from ..utils.logger import LOGGER
from ..utils.validate import valid_ref
from ..utils.version import is_newer_version
from .decorators import (
    ERR_GITHUB_RATE_LIMITED,
    marketplace_command,
    send_repository_not_found,
    send_translated_error,
)
from .repositories import repository_summary

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..base import MarketplaceManager
    from ..repositories.base import Repository


def _send_rate_limited(connection: websocket_api.ActiveConnection, msg_id: int) -> None:
    """Answer that GitHub refused the request, the rate limit ran out."""
    send_translated_error(connection, msg_id, ERR_GITHUB_RATE_LIMITED, "rate_limited")


def _send_repository_busy(
    connection: websocket_api.ActiveConnection, msg_id: int, repository: Repository
) -> None:
    """Answer that the repository is being installed, it is not an error to log."""
    send_translated_error(
        connection,
        msg_id,
        "repository_busy",
        "repository_busy",
        {"repository": repository.data.full_name},
    )


def _send_refresh_failed(
    connection: websocket_api.ActiveConnection,
    msg_id: int,
    repository: Repository,
    exception: MarketplaceError,
) -> None:
    """Answer that the information of the repository could not be updated."""
    repository.logger.error("%s %s", repository.string, exception)
    send_translated_error(
        connection,
        msg_id,
        "error",
        "refresh_failed",
        {"repository": repository.data.full_name, "error": str(exception)},
    )


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
            if not repository.additional_info:
                repository.additional_info = (
                    await repository.async_get_readme_contents()
                )
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
                **repository_summary(marketplace, repository),
                "additional_info": repository.additional_info,
                "beta": repository.data.show_beta,
                "default_branch": repository.data.default_branch,
                "hide_default_branch": repository.repository_manifest.hide_default_branch,
                "issues": repository.data.open_issues,
                "releases": repository.data.published_tags,
                "ref": repository.ref,
                "replaces_built_in": await repository.async_replaces_built_in(),
                "selected_tag": repository.data.selected_tag,
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
        probatio.Required("type"): "marketplace/repository/version",
        probatio.Required("repository"): cv.string,
        probatio.Required("version"): valid_ref,
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
    except GitHubAnonymousRateLimitError:
        repository.data.selected_tag = selected_tag
        _send_rate_limited(connection, msg["id"])
        return
    except MarketplaceError as exception:
        repository.data.selected_tag = selected_tag
        _send_refresh_failed(connection, msg["id"], repository, exception)
        return

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
    except GitHubAnonymousRateLimitError:
        repository.data.show_beta = show_beta
        _send_rate_limited(connection, msg["id"])
        return
    except MarketplaceError as exception:
        repository.data.show_beta = show_beta
        _send_refresh_failed(connection, msg["id"], repository, exception)
        return

    await marketplace.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/install",
        probatio.Required("repository"): cv.string,
        probatio.Optional("version"): valid_ref,
        probatio.Optional("confirm_replace_built_in", default=False): cv.boolean,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command(requires_accepted_warning=True)
async def marketplace_repository_install(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Install a repository, or another version of it."""
    repository = marketplace.repositories.get_by_id(msg["repository"])
    if repository is None:
        send_repository_not_found(connection, msg["id"], msg["repository"])
        return

    try:
        was_installed = repository.data.installed
        try:
            await repository.async_install_repository(
                ref=msg.get("version"),
                confirm_replace_built_in=msg["confirm_replace_built_in"],
            )
        finally:
            # Also when a step after writing the files failed, they are installed
            if not was_installed and repository.data.installed:
                async_dispatcher_send(hass, SIGNAL_REPOSITORY_INSTALLED, repository)

        connection.send_message(websocket_api.result_message(msg["id"], {}))
    except GitHubAnonymousRateLimitError:
        _send_rate_limited(connection, msg["id"])
    except ReplacesBuiltInNotConfirmedError as exception:
        # Confirmed with the first install, updates replace the same integration
        send_translated_error(
            connection,
            msg["id"],
            "replaces_built_in",
            "replaces_built_in_not_confirmed",
            {"repository": repository.data.full_name, "domain": exception.domain},
        )
    except RepositoryBusyError:
        _send_repository_busy(connection, msg["id"], repository)
    except MarketplaceError as exception:
        repository.logger.error("%s %s", repository.string, exception)
        send_translated_error(
            connection,
            msg["id"],
            "error",
            "install_failed",
            {"repository": repository.data.full_name, "error": str(exception)},
        )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/repository/uninstall",
        probatio.Required("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_repository_uninstall(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Uninstall a repository."""
    repository = marketplace.repositories.get_by_id(msg["repository"])
    if repository is None:
        send_repository_not_found(connection, msg["id"], msg["repository"])
        return

    if repository.installing:
        _send_repository_busy(connection, msg["id"], repository)
        return

    # Its config entries run the installed code, ignored ones too, they go first
    if (
        repository.data.category == RepositoryCategory.INTEGRATION
        and repository.data.domain
        and hass.config_entries.async_entries(repository.data.domain)
    ):
        send_translated_error(
            connection,
            msg["id"],
            "repository_in_use",
            "repository_in_use",
            {"repository": repository.data.full_name},
        )
        return

    repository.data.new = False
    # What is on disk is enough to uninstall it, GitHub is only asked when it can be,
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
    except RepositoryBusyError:
        _send_repository_busy(connection, msg["id"], repository)
        return
    except MarketplaceError:
        send_translated_error(
            connection,
            msg["id"],
            "uninstall_failed",
            "uninstall_failed",
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
    except GitHubAnonymousRateLimitError:
        _send_rate_limited(connection, msg["id"])
        return
    except MarketplaceError as exception:
        _send_refresh_failed(connection, msg["id"], repository, exception)
        return

    await marketplace.data.async_write()
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
                or is_newer_version(x.tag_name, repository.data.installed_version)
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
    except GitHubAnonymousRateLimitError:
        _send_rate_limited(connection, msg["id"])
        return
    except MarketplaceError as exception:
        # A connected rate limit is expected, and connecting would not help
        if not isinstance(exception, GitHubRateLimitError):
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
