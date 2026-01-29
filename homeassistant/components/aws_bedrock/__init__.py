"""The AWS Bedrock integration."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT,
    DOMAIN,
    LOGGER,
)

PLATFORMS = (Platform.AI_TASK, Platform.CONVERSATION)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AWSBedrockConfigEntry = ConfigEntry[Any]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up AWS Bedrock."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AWSBedrockConfigEntry) -> bool:
    """Set up AWS Bedrock from a config entry."""

    def create_and_validate_client() -> BaseClient:
        """Create and validate Bedrock client."""
        # Validate credentials using bedrock client
        bedrock_client = boto3.client(
            "bedrock",
            aws_access_key_id=entry.data[CONF_ACCESS_KEY_ID],
            aws_secret_access_key=entry.data[CONF_SECRET_ACCESS_KEY],
            region_name=entry.data.get(CONF_REGION, DEFAULT[CONF_REGION]),
        )
        bedrock_client.list_foundation_models(byOutputModality="TEXT")

        # Create runtime client for actual inference
        return boto3.client(
            "bedrock-runtime",
            aws_access_key_id=entry.data[CONF_ACCESS_KEY_ID],
            aws_secret_access_key=entry.data[CONF_SECRET_ACCESS_KEY],
            region_name=entry.data.get(CONF_REGION, DEFAULT[CONF_REGION]),
        )

    try:
        client = await hass.async_add_executor_job(create_and_validate_client)
    except ClientError as err:
        error_code = err.response.get("Error", {}).get("Code", "")
        if error_code in ("InvalidSignatureException", "UnrecognizedClientException"):
            LOGGER.error("Invalid AWS credentials: %s", err)
            return False
        raise ConfigEntryNotReady(err) from err
    except BotoCoreError as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload AWS Bedrock."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: AWSBedrockConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
