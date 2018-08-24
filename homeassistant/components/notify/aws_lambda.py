"""
AWS Lambda platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.aws_lambda/
"""
import logging
import json
import base64

import voluptuous as vol

from homeassistant.const import (
    CONF_PLATFORM, CONF_NAME)
from homeassistant.components.notify import (
    ATTR_TARGET, PLATFORM_SCHEMA, BaseNotificationService)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.json import JSONEncoder

REQUIREMENTS = ['boto3==1.4.7']

_LOGGER = logging.getLogger(__name__)

CONF_REGION = 'region_name'
CONF_ACCESS_KEY_ID = 'aws_access_key_id'
CONF_SECRET_ACCESS_KEY = 'aws_secret_access_key'
CONF_PROFILE_NAME = 'profile_name'
CONF_CONTEXT = 'context'
ATTR_CREDENTIALS = 'credentials'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_REGION, default='us-east-1'): cv.string,
    vol.Inclusive(CONF_ACCESS_KEY_ID, ATTR_CREDENTIALS): cv.string,
    vol.Inclusive(CONF_SECRET_ACCESS_KEY, ATTR_CREDENTIALS): cv.string,
    vol.Exclusive(CONF_PROFILE_NAME, ATTR_CREDENTIALS): cv.string,
    vol.Optional(CONF_CONTEXT, default=dict()): vol.Coerce(dict)
})


def get_service(hass, config, discovery_info=None):
    """Get the AWS Lambda notification service."""
    context_str = json.dumps({'hass': hass.config.as_dict(),
                              'custom': config[CONF_CONTEXT]}, cls=JSONEncoder)
    context_b64 = base64.b64encode(context_str.encode('utf-8'))
    context = context_b64.decode('utf-8')

    import boto3

    aws_config = config.copy()

    del aws_config[CONF_PLATFORM]
    del aws_config[CONF_NAME]
    del aws_config[CONF_CONTEXT]

    profile = aws_config.get(CONF_PROFILE_NAME)

    if profile is not None:
        boto3.setup_default_session(profile_name=profile)
        del aws_config[CONF_PROFILE_NAME]

    lambda_client = boto3.client("lambda", **aws_config)

    return AWSLambda(lambda_client, context)


class AWSLambda(BaseNotificationService):
    """Implement the notification service for the AWS Lambda service."""

    def __init__(self, lambda_client, context):
        """Initialize the service."""
        self.client = lambda_client
        self.context = context

    def send_message(self, message="", **kwargs):
        """Send notification to specified LAMBDA ARN."""
        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            _LOGGER.info("At least 1 target is required")
            return

        for target in targets:
            cleaned_kwargs = dict((k, v) for k, v in kwargs.items() if v)
            payload = {"message": message}
            payload.update(cleaned_kwargs)

            self.client.invoke(FunctionName=target,
                               Payload=json.dumps(payload),
                               ClientContext=self.context)
