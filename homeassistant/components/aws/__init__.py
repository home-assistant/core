"""Support for Amazon Web Services (AWS)."""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
import logging
from typing import Any

from aiobotocore.session import AioSession
import probatio

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CREDENTIALS,
    CONF_NAME,
    CONF_PROFILE_NAME,
    CONF_SERVICE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

# Loading the config flow file will register the flow
from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_CONTEXT,
    CONF_CREDENTIAL_NAME,
    CONF_CREDENTIALS,
    CONF_NOTIFY,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    CONF_VALIDATE,
    DATA_AWS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class AWSData:
    """Runtime data for the AWS integration."""

    hass_config: ConfigType
    config: dict[str, Any]
    sessions: OrderedDict[str, AioSession]


AWS_CREDENTIAL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): cv.string,
        probatio.Inclusive(CONF_ACCESS_KEY_ID, ATTR_CREDENTIALS): cv.string,
        probatio.Inclusive(CONF_SECRET_ACCESS_KEY, ATTR_CREDENTIALS): cv.string,
        probatio.Exclusive(CONF_PROFILE_NAME, ATTR_CREDENTIALS): cv.string,
        probatio.Optional(CONF_VALIDATE, default=True): cv.boolean,
    }
)

DEFAULT_CREDENTIAL = [
    {CONF_NAME: "default", CONF_PROFILE_NAME: "default", CONF_VALIDATE: False}
]

SUPPORTED_SERVICES = ["lambda", "sns", "sqs", "events"]

NOTIFY_PLATFORM_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_NAME): cv.string,
        probatio.Required(CONF_SERVICE): probatio.All(
            cv.string, probatio.Lower, probatio.In(SUPPORTED_SERVICES)
        ),
        probatio.Required(CONF_REGION): probatio.All(cv.string, probatio.Lower),
        probatio.Inclusive(CONF_ACCESS_KEY_ID, ATTR_CREDENTIALS): cv.string,
        probatio.Inclusive(CONF_SECRET_ACCESS_KEY, ATTR_CREDENTIALS): cv.string,
        probatio.Exclusive(CONF_PROFILE_NAME, ATTR_CREDENTIALS): cv.string,
        probatio.Exclusive(CONF_CREDENTIAL_NAME, ATTR_CREDENTIALS): cv.string,
        probatio.Optional(CONF_CONTEXT): probatio.Coerce(dict),
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Optional(
                    CONF_CREDENTIALS, default=DEFAULT_CREDENTIAL
                ): probatio.All(cv.ensure_list, [AWS_CREDENTIAL_SCHEMA]),
                probatio.Optional(CONF_NOTIFY, default=[]): probatio.All(
                    cv.ensure_list, [NOTIFY_PLATFORM_SCHEMA]
                ),
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up AWS integration."""
    if (conf := config.get(DOMAIN)) is None:
        # create a default conf using default profile
        conf = CONFIG_SCHEMA({ATTR_CREDENTIALS: DEFAULT_CREDENTIAL})

    hass.data[DATA_AWS] = AWSData(
        hass_config=config, config=conf, sessions=OrderedDict()
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry.

    Validate and save sessions per aws credential.
    """
    data = hass.data[DATA_AWS]
    conf = data.config

    if entry.source == config_entries.SOURCE_IMPORT:
        if conf is None:
            # user removed config from configuration.yaml, abort setup
            hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
            return False

        if conf != entry.data:
            # user changed config from configuration.yaml, use conf to setup
            hass.config_entries.async_update_entry(entry, data=conf)

    if conf is None:
        conf = CONFIG_SCHEMA({DOMAIN: entry.data})[DOMAIN]

    # validate credentials and create sessions
    validation = True
    tasks = [_validate_aws_credentials(hass, cred) for cred in conf[ATTR_CREDENTIALS]]
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for index, result in enumerate(results):
            name = conf[ATTR_CREDENTIALS][index][CONF_NAME]
            if isinstance(result, Exception):
                _LOGGER.error(
                    "Validating credential [%s] failed: %s",
                    name,
                    result,
                    exc_info=result,
                )
                validation = False
            else:
                data.sessions[name] = result

    # set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    for notify_config in conf[CONF_NOTIFY]:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, Platform.NOTIFY, DOMAIN, notify_config, data.hass_config
            )
        )

    return validation


async def _validate_aws_credentials(hass, credential):
    """Validate AWS credential config."""
    aws_config = credential.copy()
    del aws_config[CONF_NAME]
    del aws_config[CONF_VALIDATE]

    if (profile := aws_config.get(CONF_PROFILE_NAME)) is not None:
        session = AioSession(profile=profile)
        del aws_config[CONF_PROFILE_NAME]
        if CONF_ACCESS_KEY_ID in aws_config:
            del aws_config[CONF_ACCESS_KEY_ID]
        if CONF_SECRET_ACCESS_KEY in aws_config:
            del aws_config[CONF_SECRET_ACCESS_KEY]
    else:
        session = AioSession()

    if credential[CONF_VALIDATE]:
        async with session.create_client("iam", **aws_config) as client:
            await client.get_user()

    return session
