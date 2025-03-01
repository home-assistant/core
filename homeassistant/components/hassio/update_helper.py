"""Update helpers for Supervisor."""

from __future__ import annotations

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import HomeAssistantUpdateOptions, StoreAddonUpdate

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .handler import get_supervisor_client


async def update_addon(
    hass: HomeAssistant,
    addon: str,
    backup: bool,
    addon_name: str | None,
    installed_version: str | None,
) -> None:
    """Update an addon.

    Optionally make a backup before updating.
    """
    client = get_supervisor_client(hass)

    if backup:
        # pylint: disable-next=import-outside-toplevel
        from .backup import backup_addon_before_update

        await backup_addon_before_update(hass, addon, addon_name, installed_version)

    try:
        await client.store.update_addon(addon, StoreAddonUpdate(backup=False))
    except SupervisorError as err:
        raise HomeAssistantError(
            f"Error updating {addon_name or addon}: {err}"
        ) from err


async def update_core(hass: HomeAssistant, version: str | None, backup: bool) -> None:
    """Update core.

    Optionally make a backup before updating.
    """
    client = get_supervisor_client(hass)

    if backup:
        # pylint: disable-next=import-outside-toplevel
        from .backup import backup_core_before_update

        await backup_core_before_update(hass)

    try:
        await client.homeassistant.update(
            HomeAssistantUpdateOptions(version=version, backup=False)
        )
    except SupervisorError as err:
        raise HomeAssistantError(f"Error updating Home Assistant Core: {err}") from err
