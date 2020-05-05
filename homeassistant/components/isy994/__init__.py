"""Support the ISY-994 controllers."""
from urllib.parse import urlparse

import PyISY
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import (
    _LOGGER,
    CONF_ENABLE_CLIMATE,
    CONF_IGNORE_STRING,
    CONF_SENSOR_STRING,
    CONF_TLS_VER,
    DEFAULT_IGNORE_STRING,
    DEFAULT_SENSOR_STRING,
    DOMAIN,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY994_WEATHER,
    SUPPORTED_PLATFORMS,
    SUPPORTED_PROGRAM_PLATFORMS,
)
from .helpers import _categorize_nodes, _categorize_programs, _categorize_weather

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.url,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TLS_VER): vol.Coerce(float),
                vol.Optional(
                    CONF_IGNORE_STRING, default=DEFAULT_IGNORE_STRING
                ): cv.string,
                vol.Optional(
                    CONF_SENSOR_STRING, default=DEFAULT_SENSOR_STRING
                ): cv.string,
                vol.Optional(CONF_ENABLE_CLIMATE, default=True): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ISY 994 platform."""
    hass.data[ISY994_NODES] = {}
    for platform in SUPPORTED_PLATFORMS:
        hass.data[ISY994_NODES][platform] = []

    hass.data[ISY994_WEATHER] = []

    hass.data[ISY994_PROGRAMS] = {}
    for platform in SUPPORTED_PROGRAM_PLATFORMS:
        hass.data[ISY994_PROGRAMS][platform] = []

    isy_config = config.get(DOMAIN)

    user = isy_config.get(CONF_USERNAME)
    password = isy_config.get(CONF_PASSWORD)
    tls_version = isy_config.get(CONF_TLS_VER)
    host = urlparse(isy_config.get(CONF_HOST))
    ignore_identifier = isy_config.get(CONF_IGNORE_STRING)
    sensor_identifier = isy_config.get(CONF_SENSOR_STRING)
    enable_climate = isy_config.get(CONF_ENABLE_CLIMATE)

    if host.scheme == "http":
        https = False
        port = host.port or 80
    elif host.scheme == "https":
        https = True
        port = host.port or 443
    else:
        _LOGGER.error("isy994 host value in configuration is invalid")
        return False

    # Connect to ISY controller.
    isy = PyISY.ISY(
        host.hostname,
        port,
        username=user,
        password=password,
        use_https=https,
        tls_ver=tls_version,
        log=_LOGGER,
    )
    if not isy.connected:
        return False

    _categorize_nodes(hass, isy.nodes, ignore_identifier, sensor_identifier)
    _categorize_programs(hass, isy.programs)

    if enable_climate and isy.configuration.get("Weather Information"):
        _categorize_weather(hass, isy.climate)

    def stop(event: object) -> None:
        """Stop ISY auto updates."""
        isy.auto_update = False

    # Listen for HA stop to disconnect.
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop)

    # Load platforms for the devices in the ISY controller that we support.
    for platform in SUPPORTED_PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    isy.auto_update = True
    return True
