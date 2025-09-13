"""Integration to offer AI tasks to Home Assistant."""

import logging
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_DESCRIPTION, CONF_SELECTOR
from homeassistant.core import (
    HassJobType,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv, selector, storage
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType

from .const import (
    ATTR_ATTACHMENTS,
    ATTR_INSTRUCTIONS,
    ATTR_REQUIRED,
    ATTR_STRUCTURE,
    ATTR_TASK_NAME,
    DATA_COMPONENT,
    DATA_IMAGES,
    DATA_PREFERENCES,
    DOMAIN,
    SERVICE_GENERATE_DATA,
    SERVICE_GENERATE_IMAGE,
    AITaskEntityFeature,
)
from .entity import AITaskEntity
from .http import async_setup as async_setup_http
from .task import (
    GenDataTask,
    GenDataTaskResult,
    GenImageTask,
    GenImageTaskResult,
    ImageData,
    async_generate_data,
    async_generate_image,
)

__all__ = [
    "DOMAIN",
    "AITaskEntity",
    "AITaskEntityFeature",
    "GenDataTask",
    "GenDataTaskResult",
    "GenImageTask",
    "GenImageTaskResult",
    "ImageData",
    "async_generate_data",
    "async_generate_image",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

STRUCTURE_FIELD_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DESCRIPTION): str,
        vol.Optional(ATTR_REQUIRED): bool,
        vol.Required(CONF_SELECTOR): selector.validate_selector,
    }
)


def _validate_structure_fields(value: dict[str, Any]) -> vol.Schema:
    """Validate the structure fields as a voluptuous Schema."""
    if not isinstance(value, dict):
        raise vol.Invalid("Structure must be a dictionary")
    fields = {}
    for k, v in value.items():
        field_class = vol.Required if v.get(ATTR_REQUIRED, False) else vol.Optional
        fields[field_class(k, description=v.get(CONF_DESCRIPTION))] = selector.selector(
            v[CONF_SELECTOR]
        )
    return vol.Schema(fields, extra=vol.PREVENT_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    entity_component = EntityComponent[AITaskEntity](_LOGGER, DOMAIN, hass)
    hass.data[DATA_COMPONENT] = entity_component
    hass.data[DATA_PREFERENCES] = AITaskPreferences(hass)
    hass.data[DATA_IMAGES] = {}
    await hass.data[DATA_PREFERENCES].async_load()
    async_setup_http(hass)
    hass.http.register_view(ImageView)
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_DATA,
        async_service_generate_data,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TASK_NAME): cv.string,
                vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
                vol.Required(ATTR_INSTRUCTIONS): cv.string,
                vol.Optional(ATTR_STRUCTURE): vol.All(
                    vol.Schema({str: STRUCTURE_FIELD_SCHEMA}),
                    _validate_structure_fields,
                ),
                vol.Optional(ATTR_ATTACHMENTS): vol.All(
                    cv.ensure_list, [selector.MediaSelector({"accept": ["*/*"]})]
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
        job_type=HassJobType.Coroutinefunction,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_IMAGE,
        async_service_generate_image,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TASK_NAME): cv.string,
                vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
                vol.Required(ATTR_INSTRUCTIONS): cv.string,
                vol.Optional(ATTR_ATTACHMENTS): vol.All(
                    cv.ensure_list, [selector.MediaSelector({"accept": ["*/*"]})]
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
        job_type=HassJobType.Coroutinefunction,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


async def async_service_generate_data(call: ServiceCall) -> ServiceResponse:
    """Run the data task service."""
    result = await async_generate_data(hass=call.hass, **call.data)
    return result.as_dict()


async def async_service_generate_image(call: ServiceCall) -> ServiceResponse:
    """Run the image task service."""
    return await async_generate_image(hass=call.hass, **call.data)


class AITaskPreferences:
    """AI Task preferences."""

    KEYS = ("gen_data_entity_id", "gen_image_entity_id")

    gen_data_entity_id: str | None = None
    gen_image_entity_id: str | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the preferences."""
        self._store: storage.Store[dict[str, str | None]] = storage.Store(
            hass, 1, DOMAIN
        )

    async def async_load(self) -> None:
        """Load the data from the store."""
        data = await self._store.async_load()
        if data is None:
            return
        for key in self.KEYS:
            setattr(self, key, data.get(key))

    @callback
    def async_set_preferences(
        self,
        *,
        gen_data_entity_id: str | None | UndefinedType = UNDEFINED,
        gen_image_entity_id: str | None | UndefinedType = UNDEFINED,
    ) -> None:
        """Set the preferences."""
        changed = False
        for key, value in (
            ("gen_data_entity_id", gen_data_entity_id),
            ("gen_image_entity_id", gen_image_entity_id),
        ):
            if value is not UNDEFINED:
                if getattr(self, key) != value:
                    setattr(self, key, value)
                    changed = True

        if not changed:
            return

        self._store.async_delay_save(self.as_dict, 10)

    @callback
    def as_dict(self) -> dict[str, str | None]:
        """Get the current preferences."""
        return {key: getattr(self, key) for key in self.KEYS}


class ImageView(HomeAssistantView):
    """View to generated images."""

    url = f"/api/{DOMAIN}/images/{{filename}}"
    name = f"api:{DOMAIN}/images"

    async def get(
        self,
        request: web.Request,
        filename: str,
    ) -> web.Response:
        """Serve image."""
        hass = request.app[KEY_HASS]
        image_storage = hass.data[DATA_IMAGES]
        image_data = image_storage.get(filename)

        if image_data is None:
            raise web.HTTPNotFound

        return web.Response(
            body=image_data.data,
            content_type=image_data.mime_type,
        )
