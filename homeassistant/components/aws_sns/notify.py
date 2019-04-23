"""
AWS SNS platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.aws_sns/
"""
import json
import logging

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_PLATFORM
import homeassistant.helpers.config_validation as cv

from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA,
    BaseNotificationService)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ["boto3==1.9.16"]

CONF_REGION = 'region_name'
CONF_ACCESS_KEY_ID = 'aws_access_key_id'
CONF_SECRET_ACCESS_KEY = 'aws_secret_access_key'
CONF_PROFILE_NAME = 'profile_name'
ATTR_CREDENTIALS = 'credentials'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_REGION, default='us-east-1'): cv.string,
    vol.Inclusive(CONF_ACCESS_KEY_ID, ATTR_CREDENTIALS): cv.string,
    vol.Inclusive(CONF_SECRET_ACCESS_KEY, ATTR_CREDENTIALS): cv.string,
    vol.Exclusive(CONF_PROFILE_NAME, ATTR_CREDENTIALS): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the AWS SNS notification service."""
    _LOGGER.warning(
        "aws_sns notify platform is deprecated, please replace it"
        " with aws component. This config will become invalid in version 0.92."
        " See https://www.home-assistant.io/components/aws/ for details."
    )

    import boto3

    aws_config = config.copy()

    del aws_config[CONF_PLATFORM]
    del aws_config[CONF_NAME]

    profile = aws_config.get(CONF_PROFILE_NAME)

    if profile is not None:
        boto3.setup_default_session(profile_name=profile)
        del aws_config[CONF_PROFILE_NAME]

    sns_client = boto3.client("sns", **aws_config)

    return AWSSNS(sns_client)


class AWSSNS(BaseNotificationService):
    """Implement the notification service for the AWS SNS service."""

    def __init__(self, sns_client):
        """Initialize the service."""
        self.client = sns_client

    def send_message(self, message="", **kwargs):
        """Send notification to specified SNS ARN."""
        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            _LOGGER.info("At least 1 target is required")
            return

        message_attributes = {k: {"StringValue": json.dumps(v),
                                  "DataType": "String"}
                              for k, v in kwargs.items() if v}
        for target in targets:
            self.client.publish(TargetArn=target, Message=message,
                                Subject=kwargs.get(ATTR_TITLE,
                                                   ATTR_TITLE_DEFAULT),
                                MessageAttributes=message_attributes)
