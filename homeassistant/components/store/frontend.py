"""Starting setup task: Frontend."""

from typing import TYPE_CHECKING

from homeassistant.components.frontend import (
    async_panel_exists,
    async_register_built_in_panel,
)

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .base import HacsBase


async def async_register_frontend(hass: HomeAssistant, hacs: HacsBase) -> None:
    """Register the frontend."""
    # Add to sidepanel if needed
    if not async_panel_exists(hass, DOMAIN):
        async_register_built_in_panel(
            hass,
            "store",
            # The frontend translates this title, using the `panel.store` key
            sidebar_title="store",
            sidebar_icon="mdi:store",
            require_admin=True,
        )

    # Setup plugin endpoint if needed
    await hacs.async_setup_frontend_endpoint_plugin()
