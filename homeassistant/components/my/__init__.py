"""Support for my.home-assistant.io redirect service."""

DOMAIN = "my"
URL_PATH = "_my_redirect"


async def async_setup(hass, config):
    """Register hidden _my_redirect panel."""
    hass.components.frontend.async_register_built_in_panel(
        DOMAIN, frontend_url_path=URL_PATH
    )
    return True
