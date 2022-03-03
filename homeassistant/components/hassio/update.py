"""Update support for the Supervisor integration."""

from typing import Any

from awesomeversion import AwesomeVersion

from homeassistant.components.update import IntegrationUpdateFailed, UpdateDescription
from homeassistant.const import __version__ as CORE_VERSION
from homeassistant.core import HomeAssistant

from . import get_os_info, get_supervisor_info
from .const import DOMAIN
from .handler import HassIO

CORE_VERSION_OBJ = AwesomeVersion(CORE_VERSION)


async def async_list_updates(hass: HomeAssistant) -> list[UpdateDescription]:
    """List all updates available."""
    updates = []
    supervisor: HassIO = hass.data[DOMAIN]

    await supervisor.refresh_updates()
    available_updates = await supervisor.get_available_updates()

    supervisor_info = get_supervisor_info(hass)
    os_info = get_os_info(hass)

    for update in available_updates["available_updates"]:
        if update["update_type"] == "core":
            version_latest = AwesomeVersion(update["version_latest"])
            if version_latest.dev:
                changelog = "https://github.com/home-assistant/core/commits/dev"
            elif version_latest.beta:
                changelog = "https://rc.home-assistant.io/latest-release-notes/"
            else:
                changelog = "https://www.home-assistant.io/latest-release-notes/"

            updates.append(
                UpdateDescription(
                    identifier="core",
                    name="Home Assistant Core",
                    current_version=CORE_VERSION_OBJ.string,
                    available_version=version_latest.string,
                    changelog_url=changelog,
                    supports_backup=True,
                )
            )

        elif update["update_type"] == "supervisor":
            version_latest = AwesomeVersion(update["version_latest"])
            if version_latest.dev:
                changelog = "https://github.com/home-assistant/supervisor/commits/main"
            else:
                changelog = f"https://github.com/home-assistant/supervisor/releases/tag/{version_latest.string}"

            updates.append(
                UpdateDescription(
                    identifier="supervisor",
                    name="Home Assistant Supervisor",
                    current_version=supervisor_info["version"],
                    available_version=version_latest.string,
                    changelog_url=changelog,
                )
            )
        elif update["update_type"] == "os":
            version_latest = AwesomeVersion(update["version_latest"])
            if version_latest.dev:
                changelog = (
                    "https://github.com/home-assistant/operating-system/commits/dev"
                )
            else:
                changelog = f"https://github.com/home-assistant/operating-system/releases/tag/{version_latest.string}"

            updates.append(
                UpdateDescription(
                    identifier="os",
                    name="Home Assistant Operating System",
                    current_version=os_info["version"],
                    available_version=version_latest.string,
                    changelog_url=changelog,
                )
            )
        else:
            addon_info = next(
                (
                    addon
                    for addon in supervisor_info["addons"]
                    if addon["name"] == update["name"]
                ),
                None,
            )
            if not addon_info:
                continue

            slug = addon_info["slug"]

            changelog = await supervisor.send_command(
                f"/addons/{slug}/changelog",
                method="get",
                json_return=False,
            )

            updates.append(
                UpdateDescription(
                    identifier=f"addon-{slug}",
                    name=update["name"],
                    current_version=addon_info["version"],
                    available_version=update["version_latest"],
                    icon_url=f"/api/hassio/addons/{slug}/icon",
                    changelog_content=changelog,
                    supports_backup=True,
                )
            )
    return updates


async def async_perform_update(
    hass: HomeAssistant,
    identifier: str,
    version: str,
    **kwargs: Any,
) -> None:
    """Perform an update."""
    backup = kwargs.get("backup")
    supervisor: HassIO = hass.data[DOMAIN]

    if identifier == "core":
        await supervisor.send_command(
            "/core/update",
            payload={"version": version, "backup": backup},
            timeout=None,
        )
    elif identifier == "supervisor":
        await supervisor.send_command(
            "/supervisor/update",
            payload={"version": version},
            timeout=None,
        )
    elif identifier == "os":
        await supervisor.send_command(
            "/os/update",
            payload={"version": version},
            timeout=None,
        )
    elif identifier.startswith("addon-"):
        await supervisor.send_command(
            f"/store/addons/{identifier.split('-')[1]}/update/{version}",
            payload={"backup": backup},
            timeout=None,
        )
    else:
        raise IntegrationUpdateFailed("Unknown update identifier")
