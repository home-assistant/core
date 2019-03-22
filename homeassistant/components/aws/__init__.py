"""Support for Amazon Web Services (AWS)."""
import asyncio
import logging
from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_CREDENTIALS, CONF_NAME, CONF_PROFILE_NAME
from homeassistant.helpers import config_validation as cv, discovery

# Loading the config flow file will register the flow
from . import config_flow  # noqa
from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_SECRET_ACCESS_KEY,
    DATA_CONFIG,
    DATA_HASS_CONFIG,
    DATA_SESSIONS,
    DOMAIN,
    CONF_NOTIFY,
)
from .notify import PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA

REQUIREMENTS = ["aiobotocore==0.10.2"]

_LOGGER = logging.getLogger(__name__)

AWS_CREDENTIAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Inclusive(CONF_ACCESS_KEY_ID, ATTR_CREDENTIALS): cv.string,
        vol.Inclusive(CONF_SECRET_ACCESS_KEY, ATTR_CREDENTIALS): cv.string,
        vol.Exclusive(CONF_PROFILE_NAME, ATTR_CREDENTIALS): cv.string,
    }
)

DEFAULT_CREDENTIAL = [{CONF_NAME: "default", CONF_PROFILE_NAME: "default"}]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(
                    ATTR_CREDENTIALS, default=DEFAULT_CREDENTIAL
                ): vol.All(cv.ensure_list, [AWS_CREDENTIAL_SCHEMA]),
                vol.Optional(CONF_NOTIFY): vol.All(
                    cv.ensure_list, [NOTIFY_PLATFORM_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up AWS component."""
    hass.data[DATA_HASS_CONFIG] = config

    conf = config.get(DOMAIN)
    if conf is None:
        # create a default conf using default profile
        conf = CONFIG_SCHEMA({ATTR_CREDENTIALS: DEFAULT_CREDENTIAL})

    hass.data[DATA_CONFIG] = conf
    hass.data[DATA_SESSIONS] = OrderedDict()

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
        )
    )

    return True


async def async_setup_entry(hass, entry):
    """Load a config entry.

    Validate and save sessions per aws credential.
    """
    config = hass.data.get(DATA_HASS_CONFIG)
    conf = hass.data.get(DATA_CONFIG)

    if entry.source == config_entries.SOURCE_IMPORT:
        if conf is None:
            # user removed config from configuration.yaml, abort setup
            hass.async_create_task(
                hass.config_entries.async_remove(entry.entry_id)
            )
            return False

        if conf != entry.data:
            # user changed config from configuration.yaml, use conf to setup
            hass.config_entries.async_update_entry(entry, data=conf)

    if conf is None:
        conf = CONFIG_SCHEMA({DOMAIN: entry.data})[DOMAIN]

    validation = True
    tasks = []
    for cred in conf.get(ATTR_CREDENTIALS):
        tasks.append(_validate_aws_credentials(hass, cred))
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for index, result in enumerate(results):
            name = conf[ATTR_CREDENTIALS][index][CONF_NAME]
            if isinstance(result, Exception):
                _LOGGER.error(
                    "Validating credential [%s] failed: %s",
                    name, result, exc_info=result
                )
                validation = False
            else:
                hass.data[DATA_SESSIONS][name] = result

    # No entry support for notify component yet
    for notify_config in conf.get(CONF_NOTIFY, []):
        discovery.load_platform(hass, "notify", DOMAIN, notify_config, config)

    return validation


async def _validate_aws_credentials(hass, credential):
    """Validate AWS credential config."""
    import aiobotocore

    aws_config = credential.copy()
    del aws_config[CONF_NAME]

    profile = aws_config.get(CONF_PROFILE_NAME)

    if profile is not None:
        session = aiobotocore.AioSession(profile=profile, loop=hass.loop)
        del aws_config[CONF_PROFILE_NAME]
        if CONF_ACCESS_KEY_ID in aws_config:
            del aws_config[CONF_ACCESS_KEY_ID]
        if CONF_SECRET_ACCESS_KEY in aws_config:
            del aws_config[CONF_SECRET_ACCESS_KEY]
    else:
        session = aiobotocore.AioSession(loop=hass.loop)

    async with session.create_client("iam", **aws_config) as client:
        await client.get_user()

    return session
