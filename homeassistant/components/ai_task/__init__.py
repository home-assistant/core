"""Integration to offer AI tasks to Home Assistant."""

import logging

from homeassistant.components.media_source import local_source
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, storage
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType

from .const import DATA_COMPONENT, DATA_PREFERENCES, DOMAIN, AITaskEntityFeature
from .entity import AITaskEntity
from .http import async_setup as async_setup_http
from .media_source import async_get_media_source
from .services import async_setup_services
from .task import (
    GenDataTask,
    GenDataTaskResult,
    GenImageTask,
    GenImageTaskResult,
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
    "async_generate_data",
    "async_generate_image",
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up AI Task."""
    entity_component = EntityComponent[AITaskEntity](_LOGGER, DOMAIN, hass)
    hass.data[DATA_COMPONENT] = entity_component
    hass.data[DATA_PREFERENCES] = AITaskPreferences(hass)
    await hass.data[DATA_PREFERENCES].async_load()
    async_setup_http(hass)
    if hass.config.media_dirs:
        source = await async_get_media_source(hass)
        hass.http.register_view(local_source.LocalMediaView(hass, source))
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


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
        gen_data_entity_id: str | UndefinedType | None = UNDEFINED,
        gen_image_entity_id: str | UndefinedType | None = UNDEFINED,
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
