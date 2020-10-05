"""The TaHoma integration."""
from collections import defaultdict
from datetime import timedelta
import logging

from aiohttp import ClientError, ServerDisconnectedError
from pyhoma.client import TahomaClient
from pyhoma.exceptions import BadCredentialsException, TooManyRequestsException
import voluptuous as vol

from homeassistant.components.scene import DOMAIN as SCENE
from homeassistant.const import CONF_EXCLUDE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_validation as cv, discovery

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, IGNORED_TAHOMA_TYPES, TAHOMA_TYPES
from .coordinator import TahomaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_EXCLUDE),
            vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(CONF_EXCLUDE, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the TaHoma component."""
    configuration = config.get(DOMAIN)

    if configuration is None:
        return False

    hass.data.setdefault(DOMAIN, {})

    username = configuration.get(CONF_USERNAME)
    password = configuration.get(CONF_PASSWORD)

    session = aiohttp_client.async_create_clientsession(hass)
    client = TahomaClient(username, password, session=session)

    try:
        await client.login()
        devices = await client.get_devices()
        scenarios = await client.get_scenarios()
    except BadCredentialsException:
        _LOGGER.error("invalid_auth")
        return False
    except TooManyRequestsException:
        _LOGGER.error("too_many_requests")
        return False
    except (TimeoutError, ClientError, ServerDisconnectedError):
        _LOGGER.error("cannot_connect")
        return False
    except Exception as exception:  # pylint: disable=broad-except
        _LOGGER.exception(exception)
        return False

    tahoma_coordinator = TahomaDataUpdateCoordinator(
        hass,
        _LOGGER,
        name="TaHoma Event Fetcher",
        client=client,
        devices=devices,
        update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
    )

    await tahoma_coordinator.async_refresh()

    entities = defaultdict(list)
    entities[SCENE] = scenarios

    hass.data[DOMAIN] = {
        "entities": entities,
        "coordinator": tahoma_coordinator,
    }

    for device in tahoma_coordinator.data.values():
        platform = TAHOMA_TYPES.get(device.widget) or TAHOMA_TYPES.get(device.ui_class)
        if platform:
            entities[platform].append(device)
        elif (
            device.widget not in IGNORED_TAHOMA_TYPES
            and device.ui_class not in IGNORED_TAHOMA_TYPES
        ):
            _LOGGER.debug(
                "Unsupported TaHoma device detected (%s - %s - %s)",
                device.controllable_name,
                device.ui_class,
                device.widget,
            )

    for platform in entities:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True
