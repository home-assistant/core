"""Home Assistant Cast integration for Cast."""

from typing import TYPE_CHECKING

from homeassistant import auth, core

if TYPE_CHECKING:
    from . import CastConfigEntry

CAST_USER_NAME = "Home Assistant Cast"


async def async_setup_ha_cast(hass: core.HomeAssistant, entry: CastConfigEntry) -> str:
    """Set up Home Assistant Cast and return its refresh token."""
    user_id: str | None = entry.data.get("user_id")
    user: auth.models.User | None = None

    if user_id is not None:
        user = await hass.auth.async_get_user(user_id)

    if user is None:
        user = await hass.auth.async_create_system_user(
            CAST_USER_NAME, group_ids=[auth.const.GROUP_ID_ADMIN]
        )
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "user_id": user.id}
        )

    if user.refresh_tokens:
        refresh_token: auth.models.RefreshToken = list(user.refresh_tokens.values())[0]
    else:
        refresh_token = await hass.auth.async_create_refresh_token(user)

    return refresh_token.token


async def async_remove_user(hass: core.HomeAssistant, entry: CastConfigEntry) -> None:
    """Remove Home Assistant Cast user."""
    user_id: str | None = entry.data.get("user_id")

    if user_id is not None and (user := await hass.auth.async_get_user(user_id)):
        await hass.auth.async_remove_user(user)
