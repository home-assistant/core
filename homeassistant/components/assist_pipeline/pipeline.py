"""Classes for voice assistant pipelines."""

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.components import conversation, stt, tts, websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.collection import (
    CollectionError,
    ItemNotFound,
    SerializedStorageCollection,
    StorageCollection,
    StorageCollectionWebsocket,
)
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType, VolDictType
from homeassistant.util import language as language_util, ulid as ulid_util

from . import error as _error, models as _models, run as _run, runtime as _runtime
from .const import DOMAIN

PipelineError = _error.PipelineError
PipelineNotFound = _error.PipelineNotFound

PIPELINE_STAGE_ORDER = _models.PIPELINE_STAGE_ORDER
AudioSettings = _models.AudioSettings
Pipeline = _models.Pipeline
PipelineEvent = _models.PipelineEvent
PipelineEventCallback = _models.PipelineEventCallback
PipelineEventType = _models.PipelineEventType
PipelineStage = _models.PipelineStage
WakeWordSettings = _models.WakeWordSettings

STORED_PIPELINE_RUNS = _run.STORED_PIPELINE_RUNS
PipelineInput = _run.PipelineInput
PipelineRun = _run.PipelineRun

KEY_ASSIST_PIPELINE = _runtime.KEY_ASSIST_PIPELINE
AssistDevice = _runtime.AssistDevice
DeviceAudioQueue = _runtime.DeviceAudioQueue
PipelineData = _runtime.PipelineData
PipelineRunDebug = _runtime.PipelineRunDebug
PipelineRuns = _runtime.PipelineRuns

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.pipelines"
STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 2

ENGINE_LANGUAGE_PAIRS = (
    ("stt_engine", "stt_language"),
    ("tts_engine", "tts_language"),
)


def validate_language(data: dict[str, Any]) -> Any:
    """Validate language settings."""
    for engine, language in ENGINE_LANGUAGE_PAIRS:
        if data[engine] is not None and data[language] is None:
            raise vol.Invalid(f"Need language {language} for {engine} {data[engine]}")
    return data


PIPELINE_FIELDS: VolDictType = {
    vol.Required("conversation_engine"): str,
    vol.Required("conversation_language"): str,
    vol.Required("language"): str,
    vol.Required("name"): str,
    vol.Required("stt_engine"): vol.Any(str, None),
    vol.Required("stt_language"): vol.Any(str, None),
    vol.Required("tts_engine"): vol.Any(str, None),
    vol.Required("tts_language"): vol.Any(str, None),
    vol.Required("tts_voice"): vol.Any(str, None),
    vol.Required("wake_word_entity"): vol.Any(str, None),
    vol.Required("wake_word_id"): vol.Any(str, None),
    vol.Optional("prefer_local_intents"): bool,
    vol.Optional("acknowledge_media_id"): str,
}


@callback
def _async_resolve_default_pipeline_settings(
    hass: HomeAssistant,
    *,
    conversation_engine_id: str | None = None,
    stt_engine_id: str | None = None,
    tts_engine_id: str | None = None,
    pipeline_name: str,
) -> dict[str, str | None]:
    """Resolve settings for a default pipeline.

    The default pipeline will use the homeassistant conversation agent and the
    default stt / tts engines if none are specified.
    """
    conversation_language = "en"
    pipeline_language = "en"
    stt_engine = None
    stt_language = None
    tts_engine = None
    tts_language = None
    tts_voice = None
    wake_word_entity = None
    wake_word_id = None

    if conversation_engine_id is None:
        conversation_engine_id = conversation.HOME_ASSISTANT_AGENT

    # Find a matching language supported by the Home Assistant conversation agent
    conversation_languages = language_util.matches(
        hass.config.language,
        conversation.async_get_conversation_languages(hass, conversation_engine_id),
        country=hass.config.country,
    )
    if conversation_languages:
        pipeline_language = hass.config.language
        conversation_language = conversation_languages[0]

    if stt_engine_id is None:
        stt_engine_id = stt.async_default_engine(hass)

    if stt_engine_id is not None:
        stt_engine = stt.async_get_speech_to_text_engine(hass, stt_engine_id)
        if stt_engine is None:
            stt_engine_id = None

    if stt_engine:
        stt_languages = language_util.matches(
            pipeline_language,
            stt_engine.supported_languages,
            country=hass.config.country,
        )
        if stt_languages:
            stt_language = stt_languages[0]
        else:
            _LOGGER.debug(
                "Speech-to-text engine '%s' does not support language '%s'",
                stt_engine_id,
                pipeline_language,
            )
            stt_engine_id = None

    if tts_engine_id is None:
        tts_engine_id = tts.async_default_engine(hass)

    if tts_engine_id is not None:
        tts_engine = tts.get_engine_instance(hass, tts_engine_id)
        if tts_engine is None:
            tts_engine_id = None

    if tts_engine:
        tts_languages = language_util.matches(
            pipeline_language,
            tts_engine.supported_languages,
            country=hass.config.country,
        )
        if tts_languages:
            tts_language = tts_languages[0]
            tts_voices = tts_engine.async_get_supported_voices(tts_language)
            if tts_voices:
                tts_voice = tts_voices[0].voice_id
        else:
            _LOGGER.debug(
                "Text-to-speech engine '%s' does not support language '%s'",
                tts_engine_id,
                pipeline_language,
            )
            tts_engine_id = None

    return {
        "conversation_engine": conversation_engine_id,
        "conversation_language": conversation_language,
        "language": hass.config.language,
        "name": pipeline_name,
        "stt_engine": stt_engine_id,
        "stt_language": stt_language,
        "tts_engine": tts_engine_id,
        "tts_language": tts_language,
        "tts_voice": tts_voice,
        "wake_word_entity": wake_word_entity,
        "wake_word_id": wake_word_id,
    }


async def _async_create_default_pipeline(
    hass: HomeAssistant, pipeline_store: PipelineStorageCollection
) -> Pipeline:
    """Create a default pipeline.

    The default pipeline will use the homeassistant conversation agent and the
    default stt / tts engines.
    """
    pipeline_settings = _async_resolve_default_pipeline_settings(
        hass, pipeline_name="Home Assistant"
    )
    return await pipeline_store.async_create_item(pipeline_settings)


async def async_create_default_pipeline(
    hass: HomeAssistant,
    stt_engine_id: str,
    tts_engine_id: str,
    pipeline_name: str,
) -> Pipeline | None:
    """Create a pipeline with default settings.

    The default pipeline will use the homeassistant conversation agent and the
    specified stt / tts engines.
    """
    pipeline_data = hass.data[KEY_ASSIST_PIPELINE]
    pipeline_store = pipeline_data.pipeline_store
    pipeline_settings = _async_resolve_default_pipeline_settings(
        hass,
        stt_engine_id=stt_engine_id,
        tts_engine_id=tts_engine_id,
        pipeline_name=pipeline_name,
    )
    if (
        pipeline_settings["stt_engine"] != stt_engine_id
        or pipeline_settings["tts_engine"] != tts_engine_id
    ):
        return None
    return await pipeline_store.async_create_item(pipeline_settings)


@callback
def _async_get_pipeline_from_conversation_entity(
    hass: HomeAssistant, entity_id: str
) -> Pipeline:
    """Get a pipeline by conversation entity ID."""
    entity = hass.states.get(entity_id)
    settings = _async_resolve_default_pipeline_settings(
        hass,
        pipeline_name=entity.name if entity else entity_id,
        conversation_engine_id=entity_id,
    )
    settings["id"] = entity_id

    return Pipeline.from_json(settings)


@callback
def async_get_pipeline(hass: HomeAssistant, pipeline_id: str | None = None) -> Pipeline:
    """Get a pipeline by id or the preferred pipeline."""
    pipeline_data = hass.data[KEY_ASSIST_PIPELINE]

    if pipeline_id is None:
        # A pipeline was not specified, use the preferred one
        pipeline_id = pipeline_data.pipeline_store.async_get_preferred_item()

    if pipeline_id.startswith("conversation."):
        return _async_get_pipeline_from_conversation_entity(hass, pipeline_id)

    pipeline = pipeline_data.pipeline_store.data.get(pipeline_id)

    # If invalid pipeline ID was specified
    if pipeline is None:
        raise PipelineNotFound(
            "pipeline_not_found", f"Pipeline {pipeline_id} not found"
        )

    return pipeline


@callback
def async_get_pipelines(hass: HomeAssistant) -> list[Pipeline]:
    """Get all pipelines."""
    pipeline_data = hass.data[KEY_ASSIST_PIPELINE]

    return list(pipeline_data.pipeline_store.data.values())


async def async_update_pipeline(
    hass: HomeAssistant,
    pipeline: Pipeline,
    *,
    conversation_engine: str | UndefinedType = UNDEFINED,
    conversation_language: str | UndefinedType = UNDEFINED,
    language: str | UndefinedType = UNDEFINED,
    name: str | UndefinedType = UNDEFINED,
    stt_engine: str | UndefinedType | None = UNDEFINED,
    stt_language: str | UndefinedType | None = UNDEFINED,
    tts_engine: str | UndefinedType | None = UNDEFINED,
    tts_language: str | UndefinedType | None = UNDEFINED,
    tts_voice: str | UndefinedType | None = UNDEFINED,
    wake_word_entity: str | UndefinedType | None = UNDEFINED,
    wake_word_id: str | UndefinedType | None = UNDEFINED,
    prefer_local_intents: bool | UndefinedType = UNDEFINED,
) -> None:
    """Update a pipeline."""
    pipeline_data = hass.data[KEY_ASSIST_PIPELINE]

    updates: dict[str, Any] = pipeline.to_json()
    updates.pop("id")
    # Refactor this once we bump to Python 3.12
    # and have https://peps.python.org/pep-0692/
    updates.update(
        {
            key: val
            for key, val in (
                ("conversation_engine", conversation_engine),
                ("conversation_language", conversation_language),
                ("language", language),
                ("name", name),
                ("stt_engine", stt_engine),
                ("stt_language", stt_language),
                ("tts_engine", tts_engine),
                ("tts_language", tts_language),
                ("tts_voice", tts_voice),
                ("wake_word_entity", wake_word_entity),
                ("wake_word_id", wake_word_id),
                ("prefer_local_intents", prefer_local_intents),
            )
            if val is not UNDEFINED
        }
    )

    await pipeline_data.pipeline_store.async_update_item(pipeline.id, updates)


class PipelinePreferred(CollectionError):
    """Raised when attempting to delete the preferred pipelen."""

    def __init__(self, item_id: str) -> None:
        """Initialize pipeline preferred error."""
        super().__init__(f"Item {item_id} preferred.")
        self.item_id = item_id


class SerializedPipelineStorageCollection(SerializedStorageCollection):
    """Serialized pipeline storage collection."""

    preferred_item: str


class PipelineStorageCollection(
    StorageCollection[Pipeline, SerializedPipelineStorageCollection]
):
    """Pipeline storage collection."""

    _preferred_item: str

    @override
    async def _async_load_data(self) -> SerializedPipelineStorageCollection | None:
        """Load the data."""
        if not (data := await super()._async_load_data()):
            pipeline = await _async_create_default_pipeline(self.hass, self)
            self._preferred_item = pipeline.id
            return data

        self._preferred_item = data["preferred_item"]

        return data

    @override
    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        validated_data: dict = validate_language(data)
        return validated_data

    @callback
    @override
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return ulid_util.ulid_now()

    @override
    async def _update_data(self, item: Pipeline, update_data: dict) -> Pipeline:
        """Return a new updated item."""
        update_data = validate_language(update_data)
        return Pipeline(id=item.id, **update_data)

    @override
    def _create_item(self, item_id: str, data: dict) -> Pipeline:
        """Create an item from validated config."""
        return Pipeline(id=item_id, **data)

    @override
    def _deserialize_item(self, data: dict) -> Pipeline:
        """Create an item from its serialized representation."""
        return Pipeline.from_json(data)

    @override
    def _serialize_item(self, item_id: str, item: Pipeline) -> dict:
        """Return the serialized representation of an item for storing."""
        return item.to_json()

    @override
    async def async_delete_item(self, item_id: str) -> None:
        """Delete item."""
        if self._preferred_item == item_id:
            raise PipelinePreferred(item_id)
        await super().async_delete_item(item_id)

    @callback
    def async_get_preferred_item(self) -> str:
        """Get the id of the preferred item."""
        return self._preferred_item

    @callback
    def async_set_preferred_item(self, item_id: str) -> None:
        """Set the preferred pipeline."""
        if item_id not in self.data:
            raise ItemNotFound(item_id)
        self._preferred_item = item_id
        self._async_schedule_save()

    @callback
    @override
    def _data_to_save(self) -> SerializedPipelineStorageCollection:
        """Return JSON-compatible date for storing to file."""
        base_data = super()._base_data_to_save()
        return {
            "items": base_data["items"],
            "preferred_item": self._preferred_item,
        }


class PipelineStorageCollectionWebsocket(
    StorageCollectionWebsocket[PipelineStorageCollection]
):
    """Class to expose storage collection management over websocket."""

    @callback
    @override
    def async_setup(self, hass: HomeAssistant) -> None:
        """Set up the websocket commands."""
        super().async_setup(hass)

        websocket_api.async_register_command(
            hass,
            f"{self.api_prefix}/get",
            self.ws_get_item,
            websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
                {
                    vol.Required("type"): f"{self.api_prefix}/get",
                    vol.Optional(self.item_id_key): str,
                }
            ),
        )

        websocket_api.async_register_command(
            hass,
            f"{self.api_prefix}/set_preferred",
            websocket_api.require_admin(
                websocket_api.async_response(self.ws_set_preferred_item)
            ),
            websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
                {
                    vol.Required("type"): f"{self.api_prefix}/set_preferred",
                    vol.Required(self.item_id_key): str,
                }
            ),
        )

    @override
    async def ws_delete_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Delete an item."""
        try:
            await super().ws_delete_item(hass, connection, msg)
        except PipelinePreferred as exc:
            connection.send_error(msg["id"], websocket_api.ERR_NOT_ALLOWED, str(exc))

    @callback
    def ws_get_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Get an item."""
        item_id = msg.get(self.item_id_key)
        if item_id is None:
            item_id = self.storage_collection.async_get_preferred_item()

        if item_id.startswith("conversation.") and hass.states.get(item_id):
            connection.send_result(
                msg["id"], _async_get_pipeline_from_conversation_entity(hass, item_id)
            )
            return

        if item_id not in self.storage_collection.data:
            connection.send_error(
                msg["id"],
                websocket_api.ERR_NOT_FOUND,
                f"Unable to find {self.item_id_key} {item_id}",
            )
            return

        connection.send_result(msg["id"], self.storage_collection.data[item_id])

    @callback
    @override
    def ws_list_item(
        self, hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """List items."""
        connection.send_result(
            msg["id"],
            {
                "pipelines": async_get_pipelines(hass),
                "preferred_pipeline": (
                    self.storage_collection.async_get_preferred_item()
                ),
            },
        )

    async def ws_set_preferred_item(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Set the preferred item."""
        try:
            self.storage_collection.async_set_preferred_item(msg[self.item_id_key])
        except ItemNotFound:
            connection.send_error(
                msg["id"], websocket_api.ERR_NOT_FOUND, "unknown item"
            )
            return
        connection.send_result(msg["id"])


class PipelineStore(Store[SerializedPipelineStorageCollection]):
    """Store pipeline data."""

    @override
    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: SerializedPipelineStorageCollection,
    ) -> SerializedPipelineStorageCollection:
        """Migrate to the new version."""
        if old_major_version == 1 and old_minor_version < 2:
            # Version 1.2 adds wake word configuration
            for pipeline in old_data["items"]:
                # Populate keys which were introduced before version 1.2
                pipeline.setdefault("wake_word_entity", None)
                pipeline.setdefault("wake_word_id", None)

        if old_major_version > 1:
            raise NotImplementedError
        return old_data


@singleton(KEY_ASSIST_PIPELINE, async_=True)
async def async_setup_pipeline_store(hass: HomeAssistant) -> PipelineData:
    """Set up the pipeline storage collection."""
    pipeline_store = PipelineStorageCollection(
        PipelineStore(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_VERSION_MINOR
        )
    )
    await pipeline_store.async_load()
    PipelineStorageCollectionWebsocket(
        pipeline_store,
        f"{DOMAIN}/pipeline",
        "pipeline",
        PIPELINE_FIELDS,
        PIPELINE_FIELDS,
    ).async_setup(hass)
    return PipelineData(pipeline_store)
