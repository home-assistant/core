"""The AWS Bedrock integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_ENABLE_WEB_SEARCH,
    CONF_GOOGLE_API_KEY,
    CONF_GOOGLE_CSE_ID,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT,
    DOMAIN,
    LOGGER,
)
from .llm_api import AWSBedrockWebSearchAPI

PLATFORMS = (Platform.AI_TASK, Platform.CONVERSATION)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

if TYPE_CHECKING:
    type AWSBedrockConfigEntry = ConfigEntry[Any]
else:
    type AWSBedrockConfigEntry = ConfigEntry


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up AWS Bedrock."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AWSBedrockConfigEntry) -> bool:
    """Set up AWS Bedrock from a config entry."""

    def create_client() -> boto3.client:
        """Create Bedrock client."""
        return boto3.client(
            "bedrock-runtime",
            aws_access_key_id=entry.data[CONF_ACCESS_KEY_ID],
            aws_secret_access_key=entry.data[CONF_SECRET_ACCESS_KEY],
            region_name=entry.data.get(CONF_REGION, DEFAULT[CONF_REGION]),
        )

    def validate_credentials() -> None:
        """Validate AWS credentials by listing foundation models."""
        # Use bedrock client (not bedrock-runtime) to validate credentials
        bedrock_client = boto3.client(
            "bedrock",
            aws_access_key_id=entry.data[CONF_ACCESS_KEY_ID],
            aws_secret_access_key=entry.data[CONF_SECRET_ACCESS_KEY],
            region_name=entry.data.get(CONF_REGION, DEFAULT[CONF_REGION]),
        )
        bedrock_client.list_foundation_models(byOutputModality="TEXT")

    try:
        # Validate credentials first
        await hass.async_add_executor_job(validate_credentials)
        # Create the runtime client for actual inference
        client = await hass.async_add_executor_job(create_client)
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

    # Register web search API if any subentry has it enabled
    web_search_registered = False
    for subentry in entry.subentries.values():
        if subentry.data.get(CONF_ENABLE_WEB_SEARCH, DEFAULT[CONF_ENABLE_WEB_SEARCH]):
            google_api_key = subentry.data.get(CONF_GOOGLE_API_KEY, "")
            google_cse_id = subentry.data.get(CONF_GOOGLE_CSE_ID, "")
            if google_api_key and google_cse_id and not web_search_registered:
                # Register the web search API
                api = AWSBedrockWebSearchAPI(hass, google_api_key, google_cse_id)
                entry.async_on_unload(llm.async_register_api(hass, api))
                web_search_registered = True
                LOGGER.debug("Registered AWS Bedrock Web Search API")
                break

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload AWS Bedrock."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: AWSBedrockConfigEntry
) -> None:
    """Update options.

    Reload is necessary to re-register the web search API with updated credentials.
    """
    await hass.config_entries.async_reload(entry.entry_id)
