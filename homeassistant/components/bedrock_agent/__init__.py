"""The Bedrock Agent integration."""

from __future__ import annotations

import base64
from functools import partial
from io import BytesIO
import json
import logging
import mimetypes
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError
from urllib.request import urlopen

import boto3
from PIL import Image
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.conversation import agent_manager
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent

from .const import (
    CONST_KEY_ID,
    CONST_KEY_SECRET,
    CONST_KNOWLEDGEBASE_ID,
    CONST_MODEL_ID,
    CONST_MODEL_LIST,
    CONST_PROMPT_CONTEXT,
    CONST_REGION,
    CONST_SERVICE_PARAM_FILENAMES,
    CONST_SERVICE_PARAM_IMAGE_URLS,
    CONST_SERVICE_PARAM_MODEL_ID,
    CONST_SERVICE_PARAM_PROMPT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
__all__ = [
    "async_setup_entry",
    "async_unload_entry",
    "options_update_listener",
    "async_process",
    "BedrockAgent",
]


# Example migration function
async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)
    if config_entry.version == 1:
        hass.config_entries.async_update_entry(
            config_entry, data=config_entry.data, minor_version=1, version=2
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bedrock Agent from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    conversation.async_set_agent(hass, entry, BedrockAgent(hass, entry))

    hass_data = dict(entry.data)
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data

    async def async_cognitive_task(call: ServiceCall) -> ServiceResponse:
        """Return answer to prompt and description of image."""
        param_model_id = call.data.get(
            CONST_SERVICE_PARAM_MODEL_ID, "anthropic.claude-3-haiku-20240307-v1:0"
        )
        param_prompt = call.data.get(CONST_SERVICE_PARAM_PROMPT)
        prompt_content = [{"type": "text", "text": param_prompt}]

        image_filenames = call.data.get(CONST_SERVICE_PARAM_FILENAMES)
        for image_filename in image_filenames or []:
            if not hass.config.is_allowed_path(image_filename):
                raise HomeAssistantError(
                    f"Cannot read `{image_filename}`, no access to path; "
                    "`allowlist_external_dirs` may need to be adjusted in "
                    "`configuration.yaml`"
                )
            if not Path(image_filename).exists():
                raise HomeAssistantError(f"`{image_filename}` does not exist")
            mime_type, _ = mimetypes.guess_type(image_filename)
            if mime_type is None or not mime_type.startswith("image"):
                raise HomeAssistantError(f"`{image_filename}` is not an image")
            file_image_data = await hass.async_add_executor_job(
                Path(image_filename).read_bytes
            )
            file_image_data_base64 = base64.b64encode(file_image_data)
            file_image_data_str = file_image_data_base64.decode("utf-8")
            prompt_content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": file_image_data_str,
                    },
                }
            )

        param_image_urls = call.data.get(CONST_SERVICE_PARAM_IMAGE_URLS)
        for param_image_url in param_image_urls or []:
            try:
                opened_url = await hass.async_add_executor_job(urlopen, param_image_url)
                url_image = Image.open(opened_url)
                buffered = BytesIO()
                url_image.save(buffered, format="JPEG")
                url_image_base64 = base64.b64encode(buffered.getvalue())
                url_image_str = url_image_base64.decode("utf-8")
                prompt_content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": url_image_str,
                        },
                    }
                )
            except HTTPError as error:  # status reason
                raise HomeAssistantError(
                    f"Cannot access file from `{param_image_url}`."
                    f"Status: `{error.status}`, Reason: `{error.reason}`"
                ) from error

        bedrock = boto3.client(
            service_name="bedrock-runtime",
            region_name=entry.data[CONST_REGION],
            aws_access_key_id=entry.data[CONST_KEY_ID],
            aws_secret_access_key=entry.data[CONST_KEY_SECRET],
        )

        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt_content}],
            }
        )

        accept = "application/json"
        contentType = "application/json"

        bedrock_response = await hass.async_add_executor_job(
            partial(
                bedrock.invoke_model,
                body=body,
                modelId=param_model_id,
                accept=accept,
                contentType=contentType,
            ),
        )

        response_body = json.loads(bedrock_response.get("body").read())
        description = response_body.get("content")[0].get("text")

        return {"text": f"{description}"}

    IMAGE_DESCRIPTION_SCHEMA = vol.Schema(
        {
            vol.Required(CONST_SERVICE_PARAM_PROMPT): str,
            vol.Optional(CONST_SERVICE_PARAM_MODEL_ID): str,
            vol.Optional(CONST_SERVICE_PARAM_IMAGE_URLS, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(CONST_SERVICE_PARAM_FILENAMES, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
        }
    )

    hass.services.async_register(
        DOMAIN,
        "cognitive_task",
        async_cognitive_task,
        schema=IMAGE_DESCRIPTION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    conversation.async_unset_agent(hass, entry)
    return True


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    # await hass.config_entries.async_reload(config_entry.entry_id)


class BedrockAgent(conversation.AbstractConversationAgent):
    """Bedrock conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.history: dict[str, list[dict]] = {}
        self.bedrock = boto3.client(
            service_name="bedrock-runtime",
            region_name=self.entry.data[CONST_REGION],
            aws_access_key_id=self.entry.data[CONST_KEY_ID],
            aws_secret_access_key=self.entry.data[CONST_KEY_SECRET],
        )
        self.bedrock_agent = boto3.client(
            service_name="bedrock-agent-runtime",
            region_name=self.entry.data[CONST_REGION],
            aws_access_key_id=self.entry.data[CONST_KEY_ID],
            aws_secret_access_key=self.entry.data[CONST_KEY_SECRET],
        )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    @staticmethod
    def supported_models() -> list[str]:
        """Return a list of supported models."""
        return CONST_MODEL_LIST

    async def async_call_bedrock(self, question) -> str:
        """Return result from Amazon Bedrock."""

        question = self.entry.options[CONST_PROMPT_CONTEXT] + question

        modelId = self.entry.options[CONST_MODEL_ID]
        knowledgebaseId = self.entry.options.get(CONST_KNOWLEDGEBASE_ID) or ""
        body = json.dumps({"prompt": question})

        if knowledgebaseId != "":
            agent_input = {"text": question}
            agent_retrieveAndGenerateConfiguration = {
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": knowledgebaseId,
                    "modelArn": modelId,
                },
                "type": "KNOWLEDGE_BASE",
            }

            bedrock_agent_response = await self.hass.async_add_executor_job(
                partial(
                    self.bedrock_agent.retrieve_and_generate,
                    input=agent_input,
                    retrieveAndGenerateConfiguration=agent_retrieveAndGenerateConfiguration,
                ),
            )

            return bedrock_agent_response["output"]["text"]

        # switch case statement
        if modelId.startswith("amazon.titan-text-express-v1"):
            body = json.dumps(
                {
                    "inputText": question,
                    "textGenerationConfig": {
                        "temperature": 0,
                        "topP": 1,
                        "maxTokenCount": 512,
                    },
                }
            )
        elif modelId.startswith("anthropic.claude"):
            body = json.dumps(
                {
                    "prompt": f"\n\nHuman:{question}\n\nAssistant:",
                    "max_tokens_to_sample": 200,
                    "temperature": 0.1,
                    "top_p": 0.9,
                }
            )
        elif modelId.startswith("ai21.j2"):
            body = json.dumps(
                {
                    "prompt": question,
                    "temperature": 0.5,
                    "topP": 0.5,
                    "maxTokens": 200,
                    "countPenalty": {"scale": 0},
                    "presencePenalty": {"scale": 0},
                    "frequencyPenalty": {"scale": 0},
                }
            )
        elif modelId.startswith("mistral.mistral-"):
            body = json.dumps(
                {
                    "prompt": f"<s>[INST] {question} [/INST]",
                    "max_tokens": 512,
                    "temperature": 0.5,
                    "top_p": 0.9,
                    "top_k": 50,
                }
            )

        accept = "application/json"
        contentType = "application/json"

        bedrock_response = await self.hass.async_add_executor_job(
            partial(
                self.bedrock.invoke_model,
                body=body,
                modelId=modelId,
                accept=accept,
                contentType=contentType,
            ),
        )

        response_body = json.loads(bedrock_response.get("body").read())
        if modelId.startswith("amazon.titan-text-express-v1"):
            answer = response_body["results"][0]["outputText"]
        elif modelId.startswith("anthropic.claude"):
            answer = response_body["completion"]
        elif modelId.startswith("ai21.j2"):
            answer = response_body["completions"][0]["data"]["text"]
        elif modelId in [
            "mistral.mistral-7b-instruct-v0:2",
            "mistral.mixtral-8x7b-instruct-v0:1",
        ]:
            answer = response_body["outputs"][0]["text"]
        else:
            answer = "Sorry I am not able to understand my underlying model."

        return answer

    async def async_process(
        self, user_input: agent_manager.ConversationInput
    ) -> agent_manager.ConversationResult:
        """Process a sentence."""
        answer = await self.async_call_bedrock(user_input.text)

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(answer)
        return agent_manager.ConversationResult(conversation_id=None, response=response)
