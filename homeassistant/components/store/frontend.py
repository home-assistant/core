"""Starting setup task: Frontend."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.frontend import (
    add_extra_js_url,
    async_register_built_in_panel,
)

from .const import DOMAIN, URL_BASE
from .utils.workarounds import async_register_static_path

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .base import HacsBase


async def async_register_frontend(hass: HomeAssistant, hacs: HacsBase) -> None:
    """Register the frontend."""

    hacs.frontend_version = "core"

    # Custom iconset
    await async_register_static_path(
        hass, f"{URL_BASE}/iconset.js", str(hacs.integration_dir / "iconset.js")
    )
    add_extra_js_url(hass, f"{URL_BASE}/iconset.js")

    # Add to sidepanel if needed
    if DOMAIN not in hass.data.get("frontend_panels", {}):
        async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title=hacs.configuration.sidepanel_title,
            sidebar_icon=hacs.configuration.sidepanel_icon,
            frontend_url_path=DOMAIN,
            config={
                "_panel_custom": {
                    "name": "hacs-frontend",
                    "embed_iframe": True,
                    "trust_external": False,
                    "js_url": f"/hacsfiles/frontend/entrypoint.js?hacstag={hacs.frontend_version}",
                }
            },
            require_admin=True,
        )

    # Setup plugin endpoint if needed
    await hacs.async_setup_frontend_endpoint_plugin()
