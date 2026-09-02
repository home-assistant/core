"""Starting setup task: Frontend."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from homeassistant.components.frontend import (
    add_extra_js_url,
    async_register_built_in_panel,
)

from .const import DOMAIN, URL_BASE
from .hacs_frontend import VERSION as FE_VERSION, locate_dir
from .utils.workarounds import async_register_static_path

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .base import HacsBase


async def async_register_frontend(hass: HomeAssistant, hacs: HacsBase) -> None:
    """Register the frontend."""

    # Register frontend
    if hacs.configuration.dev and (frontend_path := os.getenv("HACS_FRONTEND_DIR")):
        hacs.log.warning(
            "<HacsFrontend> Frontend development mode enabled. Do not run in production!"
        )
        await async_register_static_path(
            hass, f"{URL_BASE}/frontend", f"{frontend_path}/hacs_frontend", cache_headers=False
        )
        hacs.frontend_version = "dev"
    else:
        await async_register_static_path(
            hass, f"{URL_BASE}/frontend", locate_dir(), cache_headers=False
        )
        hacs.frontend_version = FE_VERSION

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
