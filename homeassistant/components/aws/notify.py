"""AWS platform for notify component."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from aiobotocore.session import AioSession

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PROFILE_NAME,
    CONF_SERVICE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_CONTEXT, CONF_CREDENTIAL_NAME, CONF_REGION, DATA_SESSIONS

_LOGGER = logging.getLogger(__name__)


async def get_available_regions(hass, service):
    """Get available regions for a service."""
    session = AioSession()
    return await session.get_available_regions(service)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> AWSNotify | None:
    """Get the AWS notification service."""
    if discovery_info is None:
        _LOGGER.error("Please config aws notify platform in aws component")
        return None

    session = None

    conf = discovery_info

    service = conf[CONF_SERVICE]
    region_name = conf[CONF_REGION]

    available_regions = await get_available_regions(hass, service)
    if region_name not in available_regions:
        _LOGGER.error(
            "Region %s is not available for %s service, must in %s",
            region_name,
            service,
            available_regions,
        )
        return None

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
        # no platform config, use the first aws component credential instead
        if hass.data[DATA_SESSIONS]:
            session = next(iter(hass.data[DATA_SESSIONS].values()))
        else:
            _LOGGER.error("Missing aws credential for %s", config[CONF_NAME])
            return None

    if session is None:
        credential_name = aws_config.get(CONF_CREDENTIAL_NAME)
        if credential_name is not None:
            session = hass.data[DATA_SESSIONS].get(credential_name)
            if session is None:
                _LOGGER.warning("No available aws session for %s", credential_name)
            del aws_config[CONF_CREDENTIAL_NAME]

    if session is None:
        if (profile := aws_config.get(CONF_PROFILE_NAME)) is not None:
            session = AioSession(profile=profile)
            del aws_config[CONF_PROFILE_NAME]
        else:
            session = AioSession()

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

    if service == "events":
        return AWSEventBridge(session, aws_config)

    # should not reach here since service was checked in schema
    return None


class AWSNotify(BaseNotificationService):
    """Implement the notification service for the AWS service."""

    def __init__(self, session, aws_config):
        """Initialize the service."""
        self.session = session
        self.aws_config = aws_config


class AWSLambda(AWSNotify):
    """Implement the notification service for the AWS Lambda service."""

    service = "lambda"

    def __init__(self, session, aws_config, context):
        """Initialize the service."""
        super().__init__(session, aws_config)
        self.context = context

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send notification to specified LAMBDA ARN."""
        if not kwargs.get(ATTR_TARGET):
            _LOGGER.error("At least one target is required")
            return

        cleaned_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        payload = {"message": message}
        payload.update(cleaned_kwargs)
        json_payload = json.dumps(payload)

        async with self.session.create_client(
            self.service, **self.aws_config
        ) as client:
            tasks = [
                client.invoke(
                    FunctionName=target,
                    Payload=json_payload,
                    ClientContext=self.context,
                )
                for target in kwargs.get(ATTR_TARGET, [])
            ]

            if tasks:
                await asyncio.gather(*tasks)


class AWSSNS(AWSNotify):
    """Implement the notification service for the AWS SNS service."""

    service = "sns"

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send notification to specified SNS ARN."""
        if not kwargs.get(ATTR_TARGET):
            _LOGGER.error("At least one target is required")
            return

        message_attributes = {}
        if data := kwargs.get(ATTR_DATA):
            message_attributes = {
                k: {"StringValue": v, "DataType": "String"}
                for k, v in data.items()
                if v is not None
            }
        subject = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        async with self.session.create_client(
            self.service, **self.aws_config
        ) as client:
            tasks = [
                client.publish(
                    TargetArn=target,
                    Message=message,
                    Subject=subject,
                    MessageAttributes=message_attributes,
                )
                for target in kwargs.get(ATTR_TARGET, [])
            ]

            if tasks:
                await asyncio.gather(*tasks)


class AWSSQS(AWSNotify):
    """Implement the notification service for the AWS SQS service."""

    service = "sqs"

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send notification to specified SQS ARN."""
        if not kwargs.get(ATTR_TARGET):
            _LOGGER.error("At least one target is required")
            return

        cleaned_kwargs = {k: v for k, v in kwargs.items() if v is not None}
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
            tasks = [
                client.send_message(
                    QueueUrl=target,
                    MessageBody=json_body,
                    MessageAttributes=message_attributes,
                )
                for target in kwargs.get(ATTR_TARGET, [])
            ]

            if tasks:
                await asyncio.gather(*tasks)


class AWSEventBridge(AWSNotify):
    """Implement the notification service for the AWS EventBridge service."""

    service = "events"

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send notification to specified EventBus."""

        cleaned_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        data = cleaned_kwargs.get(ATTR_DATA, {})
        detail = (
            json.dumps(data["detail"])
            if "detail" in data
            else json.dumps({"message": message})
        )

        async with self.session.create_client(
            self.service, **self.aws_config
        ) as client:
            entries = []
            for target in kwargs.get(ATTR_TARGET, [None]):
                entry = {
                    "Source": data.get("source", "homeassistant"),
                    "Resources": data.get("resources", []),
                    "Detail": detail,
                    "DetailType": data.get("detail_type", ""),
                }
                if target:
                    entry["EventBusName"] = target

                entries.append(entry)
            tasks = [
                client.put_events(Entries=entries[i : min(i + 10, len(entries))])
                for i in range(0, len(entries), 10)
            ]

            if tasks:
                results = await asyncio.gather(*tasks)
                for result in results:
                    for entry in result["Entries"]:
                        if len(entry.get("EventId", "")) == 0:
                            _LOGGER.error(
                                "Failed to send event: ErrorCode=%s ErrorMessage=%s",
                                entry["ErrorCode"],
                                entry["ErrorMessage"],
                            )
