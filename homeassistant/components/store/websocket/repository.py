"""Register info websocket commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import websocket_api
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from ..const import DOMAIN
from ..enums import HacsDispatchEvent
from ..exceptions import HacsException
from ..utils.version import version_left_higher_then_right

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..base import HacsBase


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hacs/repository/info",
        vol.Required("repository_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_repository_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return information about a repository."""
    hacs: HacsBase = hass.data.get(DOMAIN)
    repository_id = msg["repository_id"]
    repository = hacs.repositories.get_by_id(repository_id)
    if repository is None:
        connection.send_error(
            msg["id"],
            "repository_not_found",
            f"Repository with ID ({repository_id}) not found",
        )
        return

    if not repository.updated_info:
        try:
            await repository.update_repository(ignore_issues=True, force=True)
        except Exception as exception:  # pylint: disable=broad-except
            repository.logger.error("%s %s", repository.string, exception)
        repository.updated_info = True

    if repository.data.new:
        repository.data.new = False
        await hacs.data.async_write()

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
                "country": repository.repository_manifest.country,
                "custom": not hacs.repositories.is_default(str(repository.data.id)),
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
        vol.Required("type"): "hacs/repository/ignore",
        vol.Required("repository"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_repository_ignore(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Ignore a repository."""
    hacs: HacsBase = hass.data.get(DOMAIN)
    repository_id = msg["repository"]
    hacs.log.info("Ignoring %s", repository_id)
    repository = hacs.repositories.get_by_id(repository_id)
    if repository is None:
        connection.send_error(
            msg["id"],
            "repository_not_found",
            f"Repository with ID ({repository_id}) not found",
        )
        return

    hacs.common.ignored_repositories.add(repository.data.full_name)

    await hacs.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hacs/repository/state",
        vol.Required("repository"): cv.string,
        vol.Required("state"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_repository_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set the state of a repository"""
    hacs: HacsBase = hass.data.get(DOMAIN)
    repository = hacs.repositories.get_by_id(msg["repository"])

    repository.state = msg["state"]

    await hacs.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hacs/repository/version",
        vol.Required("repository"): cv.string,
        vol.Required("version"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_repository_version(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set the version of a repository"""
    hacs: HacsBase = hass.data.get(DOMAIN)
    repository = hacs.repositories.get_by_id(msg["repository"])

    if msg["version"] == repository.data.default_branch:
        repository.data.selected_tag = None
    else:
        repository.data.selected_tag = msg["version"]

    await repository.update_repository(force=True)
    repository.state = None

    await hacs.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hacs/repository/beta",
        vol.Required("repository"): cv.string,
        vol.Required("show_beta"): cv.boolean,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_repository_beta(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Show or hide beta versions of a repository"""
    hacs: HacsBase = hass.data.get(DOMAIN)
    repository = hacs.repositories.get_by_id(msg["repository"])

    repository.data.show_beta = msg["show_beta"]

    await repository.update_repository(force=True)
    repository.state = None

    await hacs.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hacs/repository/download",
        vol.Required("repository"): cv.string,
        vol.Optional("version"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_repository_download(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set the version of a repository"""
    hacs: HacsBase = hass.data.get(DOMAIN)
    repository = hacs.repositories.get_by_id(msg["repository"])

    try:
        was_installed = repository.data.installed
        await repository.async_download_repository(ref=msg.get("version"))
        if not was_installed:
            hacs.async_dispatch(HacsDispatchEvent.RELOAD, {"force": True})
            await hacs.async_recreate_entities()

        await hacs.data.async_write()
        connection.send_message(websocket_api.result_message(msg["id"], {}))
    except HacsException as exception:
        repository.logger.error("%s %s", repository.string, exception)
        connection.send_error(msg["id"], "error", str(exception))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hacs/repository/remove",
        vol.Required("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_repository_remove(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Remove a repository."""
    hacs: HacsBase = hass.data.get(DOMAIN)
    repository = hacs.repositories.get_by_id(msg["repository"])

    repository.data.new = False
    try:
        await repository.update_repository(ignore_issues=True, force=True)
    except Exception as exception:  # pylint: disable=broad-except
        repository.logger.error("%s %s", repository.string, exception)
    await repository.uninstall()

    await hacs.data.async_write()
    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hacs/repository/refresh",
        vol.Required("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_repository_refresh(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Refresh a repository."""
    hacs: HacsBase = hass.data.get(DOMAIN)
    repository = hacs.repositories.get_by_id(msg["repository"])

    await repository.update_repository(ignore_issues=True, force=True)
    await hacs.data.async_write()
    # Update state of update entity
    hacs.coordinators[repository.data.category].async_update_listeners()

    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hacs/repository/release_notes",
        vol.Required("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_repository_release_notes(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return release notes."""
    hacs: HacsBase = hass.data.get(DOMAIN)
    repository = hacs.repositories.get_by_id(msg["repository"])

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
                or version_left_higher_then_right(x.tag_name, repository.data.installed_version)
            ],
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hacs/repository/releases",
        vol.Required("repository_id"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_repository_releases(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return releases."""
    hacs: HacsBase = hass.data.get(DOMAIN)
    repository = hacs.repositories.get_by_id(msg["repository_id"])
    try:
        releases = await repository.async_get_releases()
    except Exception as exception:
        hacs.log.exception(exception)
        connection.send_error(msg["id"], "unknown", str(exception))
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
