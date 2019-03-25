"""AWS platform for notify component."""
import asyncio
import logging
import json
import base64

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_PLATFORM, CONF_NAME, ATTR_CREDENTIALS
from homeassistant.components.notify import (
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
    PLATFORM_SCHEMA,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.json import JSONEncoder

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_CREDENTIAL_NAME,
    CONF_PROFILE_NAME,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DATA_SESSIONS,
)

DEPENDENCIES = ["aws"]

_LOGGER = logging.getLogger(__name__)

CONF_CONTEXT = "context"
CONF_SERVICE = "service"

SUPPORTED_SERVICES = ["lambda", "sns", "sqs"]


def _in_avilable_region(config):
    """Check if region is available."""
    import aiobotocore

    session = aiobotocore.get_session()
    available_regions = session.get_available_regions(config[CONF_SERVICE])
    if config[CONF_REGION] not in available_regions:
        raise vol.Invalid(
            "Region {} is not available for {} service, mustin {}".format(
                config[CONF_REGION], config[CONF_SERVICE], available_regions
            )
        )
    return config


PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                # override notify.PLATFORM_SCHEMA.CONF_PLATFORM to Optional
                # we don't need this field when we use discovery
                vol.Optional(CONF_PLATFORM): cv.string,
                vol.Required(CONF_SERVICE): vol.All(
                    cv.string, vol.Lower, vol.In(SUPPORTED_SERVICES)
                ),
                vol.Required(CONF_REGION): vol.All(cv.string, vol.Lower),
                vol.Inclusive(CONF_ACCESS_KEY_ID, ATTR_CREDENTIALS): cv.string,
                vol.Inclusive(
                    CONF_SECRET_ACCESS_KEY, ATTR_CREDENTIALS
                ): cv.string,
                vol.Exclusive(CONF_PROFILE_NAME, ATTR_CREDENTIALS): cv.string,
                vol.Exclusive(
                    CONF_CREDENTIAL_NAME, ATTR_CREDENTIALS
                ): cv.string,
                vol.Optional(CONF_CONTEXT): vol.Coerce(dict),
            },
            extra=vol.PREVENT_EXTRA,
        ),
        _in_avilable_region,
    )
)


async def async_get_service(hass, config, discovery_info=None):
    """Get the AWS notification service."""
    import aiobotocore

    session = None

    if discovery_info is not None:
        conf = discovery_info
    else:
        conf = config

    service = conf[CONF_SERVICE]
    region_name = conf[CONF_REGION]

    aws_config = conf.copy()

    del aws_config[CONF_SERVICE]
    del aws_config[CONF_REGION]
    if CONF_PLATFORM in aws_config:
        del aws_config[CONF_PLATFORM]
    if CONF_NAME in aws_config:
        del aws_config[CONF_NAME]
    if CONF_CONTEXT in aws_config:
        del aws_config[CONF_CONTEXT]

    if not aws_config:
        # no platform config, use aws component config instead
        if hass.data[DATA_SESSIONS]:
            session = list(hass.data[DATA_SESSIONS].values())[0]
        else:
            raise ValueError(
                "No available aws session for {}".format(config[CONF_NAME])
            )

    if session is None:
        credential_name = aws_config.get(CONF_CREDENTIAL_NAME)
        if credential_name is not None:
            session = hass.data[DATA_SESSIONS].get(credential_name)
            if session is None:
                _LOGGER.warning(
                    "No available aws session for %s", credential_name
                )
            del aws_config[CONF_CREDENTIAL_NAME]

    if session is None:
        profile = aws_config.get(CONF_PROFILE_NAME)
        if profile is not None:
            session = aiobotocore.AioSession(profile=profile, loop=hass.loop)
            del aws_config[CONF_PROFILE_NAME]
        else:
            session = aiobotocore.AioSession(loop=hass.loop)

    aws_config[CONF_REGION] = region_name

    if service == "lambda":
        context_str = json.dumps(
            {"custom": conf.get(CONF_CONTEXT, {})}, cls=JSONEncoder
        )
        context_b64 = base64.b64encode(context_str.encode("utf-8"))
        context = context_b64.decode("utf-8")
        return AWSLambda(session, aws_config, context)

    if service == "sns":
        return AWSSNS(session, aws_config)

    if service == "sqs":
        return AWSSQS(session, aws_config)

    raise ValueError("Unsupported service {}".format(service))


class AWSNotify(BaseNotificationService):
    """Implement the notification service for the AWS service."""

    def __init__(self, session, aws_config):
        """Initialize the service."""
        self.session = session
        self.aws_config = aws_config

    def send_message(self, message, **kwargs):
        """Send notification."""
        raise NotImplementedError("Please call async_send_message()")

    async def async_send_message(self, message="", **kwargs):
        """Send notification."""
        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            raise HomeAssistantError("At least one target is required")


class AWSLambda(AWSNotify):
    """Implement the notification service for the AWS Lambda service."""

    service = "lambda"

    def __init__(self, session, aws_config, context):
        """Initialize the service."""
        super().__init__(session, aws_config)
        self.context = context

    async def async_send_message(self, message="", **kwargs):
        """Send notification to specified LAMBDA ARN."""
        await super().async_send_message(message, **kwargs)

        cleaned_kwargs = dict((k, v) for k, v in kwargs.items() if v)
        payload = {"message": message}
        payload.update(cleaned_kwargs)
        json_payload = json.dumps(payload)

        async with self.session.create_client(
                self.service, **self.aws_config
        ) as client:
            tasks = []
            for target in kwargs.get(ATTR_TARGET, []):
                tasks.append(
                    client.invoke(
                        FunctionName=target,
                        Payload=json_payload,
                        ClientContext=self.context,
                    )
                )

            if tasks:
                await asyncio.gather(*tasks)


class AWSSNS(AWSNotify):
    """Implement the notification service for the AWS SNS service."""

    service = "sns"

    async def async_send_message(self, message="", **kwargs):
        """Send notification to specified SNS ARN."""
        await super().async_send_message(message, **kwargs)

        message_attributes = {
            k: {"StringValue": json.dumps(v), "DataType": "String"}
            for k, v in kwargs.items()
            if v
        }
        subject = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        async with self.session.create_client(
                self.service, **self.aws_config
        ) as client:
            tasks = []
            for target in kwargs.get(ATTR_TARGET, []):
                tasks.append(
                    client.publish(
                        TargetArn=target,
                        Message=message,
                        Subject=subject,
                        MessageAttributes=message_attributes,
                    )
                )

            if tasks:
                await asyncio.gather(*tasks)


class AWSSQS(AWSNotify):
    """Implement the notification service for the AWS SQS service."""

    service = "sqs"

    async def async_send_message(self, message="", **kwargs):
        """Send notification to specified SQS ARN."""
        await super().async_send_message(message, **kwargs)

        cleaned_kwargs = dict((k, v) for k, v in kwargs.items() if v)
        message_body = {"message": message}
        message_body.update(cleaned_kwargs)
        json_body = json.dumps(message_body)
        message_attributes = {}
        for key, val in cleaned_kwargs.items():
            message_attributes[key] = {
                "StringValue": json.dumps(val),
                "DataType": "String",
            }

        async with self.session.create_client(
                self.service, **self.aws_config
        ) as client:
            tasks = []
            for target in kwargs.get(ATTR_TARGET, []):
                tasks.append(
                    client.send_message(
                        QueueUrl=target,
                        MessageBody=json_body,
                        MessageAttributes=message_attributes,
                    )
                )

            if tasks:
                await asyncio.gather(*tasks)
