"""Support for showing device locations."""
DOMAIN = "ais_help"


async def async_setup(hass, config):
    """Register the built-in help panel."""
    hass.components.frontend.async_register_built_in_panel(
        "aishelp",
        require_admin=True,
        sidebar_title="Przydatne linki",
        sidebar_icon="mdi:qrcode",
    )
    """Register the built-in doc panel."""
    hass.components.frontend.async_register_built_in_panel(
        "aisdocs",
        require_admin=True,
        sidebar_title="Dokumentacja",
        sidebar_icon="mdi:book-open",
    )

    """Register the built-in Audio panel."""
    hass.components.frontend.async_register_built_in_panel(
        "aisaudio", "Audio", "mdi:play-box"
    )

    return True
