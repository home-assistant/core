"""Support for local control of entities by emulating a Philips Hue bridge."""

from __future__ import annotations

import logging

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import KEY_HASS
from homeassistant.components.network import async_get_source_ip
from homeassistant.const import (
    CONF_ENTITIES,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .config import (
    CONF_ADVERTISE_IP,
    CONF_ADVERTISE_PORT,
    CONF_ENTITY_HIDDEN,
    CONF_ENTITY_NAME,
    CONF_EXPOSE_BY_DEFAULT,
    CONF_EXPOSED_DOMAINS,
    CONF_HOST_IP,
    CONF_LIGHTS_ALL_DIMMABLE,
    CONF_LISTEN_PORT,
    CONF_OFF_MAPS_TO_ON_DOMAINS,
    CONF_UPNP_BIND_MULTICAST,
    DEFAULT_LIGHTS_ALL_DIMMABLE,
    DEFAULT_LISTEN_PORT,
    DEFAULT_TYPE,
    TYPE_ALEXA,
    TYPE_GOOGLE,
    Config,
)
from .const import DOMAIN
from .hue_api import (
    HueAllGroupsStateView,
    HueAllLightsStateView,
    HueConfigView,
    HueFullStateView,
    HueGroupView,
    HueOneLightChangeView,
    HueOneLightStateView,
    HueUnauthorizedUser,
    HueUsernameView,
)
from .upnp import DescriptionXmlView, async_create_upnp_datagram_endpoint

_LOGGER = logging.getLogger(__name__)


CONFIG_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ENTITY_NAME): cv.string,
        vol.Optional(CONF_ENTITY_HIDDEN): cv.boolean,
    }
)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST_IP): cv.string,
                vol.Optional(CONF_LISTEN_PORT, default=DEFAULT_LISTEN_PORT): cv.port,
                vol.Optional(CONF_ADVERTISE_IP): cv.string,
                vol.Optional(CONF_ADVERTISE_PORT): cv.port,
                vol.Optional(CONF_UPNP_BIND_MULTICAST): cv.boolean,
                vol.Optional(CONF_OFF_MAPS_TO_ON_DOMAINS): cv.ensure_list,
                vol.Optional(CONF_EXPOSE_BY_DEFAULT): cv.boolean,
                vol.Optional(CONF_EXPOSED_DOMAINS): cv.ensure_list,
                vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): vol.Any(
                    TYPE_ALEXA, TYPE_GOOGLE
                ),
                vol.Optional(CONF_ENTITIES): vol.Schema(
                    {cv.entity_id: CONFIG_ENTITY_SCHEMA}
                ),
                vol.Optional(
                    CONF_LIGHTS_ALL_DIMMABLE, default=DEFAULT_LIGHTS_ALL_DIMMABLE
                ): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def start_emulated_hue_bridge(
    hass: HomeAssistant, config: Config, app: web.Application
) -> None:
    """Start the emulated hue bridge."""
    protocol = await async_create_upnp_datagram_endpoint(
        config.host_ip_addr,
        config.upnp_bind_multicast,
        config.advertise_ip,
        config.advertise_port or config.listen_port,
    )

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, config.host_ip_addr, config.listen_port)

    try:
        await site.start()
    except OSError as error:
        _LOGGER.error(
            "Failed to create HTTP server at port %d: %s", config.listen_port, error
        )
        protocol.close()
        return

    async def stop_emulated_hue_bridge(event: Event) -> None:
        """Stop the emulated hue bridge."""
        protocol.close()
        await site.stop()
        await runner.cleanup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_emulated_hue_bridge)


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    """Activate the emulated_hue component."""
    local_ip = await async_get_source_ip(hass)
    config = Config(hass, yaml_config.get(DOMAIN, {}), local_ip)
    await config.async_setup()

    app = web.Application()
    app[KEY_HASS] = hass

    # We misunderstood the startup signal. You're not allowed to change
    # anything during startup. Temp workaround.
    app._on_startup.freeze()  # noqa: SLF001
    await app.startup()

    DescriptionXmlView(config).register(hass, app, app.router)
    HueUsernameView().register(hass, app, app.router)
    HueConfigView(config).register(hass, app, app.router)
    HueUnauthorizedUser().register(hass, app, app.router)
    HueAllLightsStateView(config).register(hass, app, app.router)
    HueOneLightStateView(config).register(hass, app, app.router)
    HueOneLightChangeView(config).register(hass, app, app.router)
    HueAllGroupsStateView(config).register(hass, app, app.router)
    HueGroupView(config).register(hass, app, app.router)
    HueFullStateView(config).register(hass, app, app.router)

    async def _start(event: Event) -> None:
        """Start the bridge."""
        await start_emulated_hue_bridge(hass, config, app)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _start)

    return True
