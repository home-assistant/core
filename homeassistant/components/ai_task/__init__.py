"""Integration to offer AI tasks to Home Assistant."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HassJobType,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv, storage
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType

from .const import DATA_COMPONENT, DATA_PREFERENCES, DOMAIN, AITaskEntityFeature
from .entity import AITaskEntity
from .http import async_setup as async_setup_conversation_http
from .task import GenTextTask, GenTextTaskResult, async_generate_text

__all__ = [
    "DOMAIN",
    "AITaskEntity",
    "AITaskEntityFeature",
    "GenTextTask",
    "GenTextTaskResult",
    "async_generate_text",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    entity_component = EntityComponent[AITaskEntity](_LOGGER, DOMAIN, hass)
    hass.data[DATA_COMPONENT] = entity_component
    hass.data[DATA_PREFERENCES] = AITaskPreferences(hass)
    await hass.data[DATA_PREFERENCES].async_load()
    async_setup_conversation_http(hass)
    hass.services.async_register(
        DOMAIN,
        "generate_text",
        async_service_generate_text,
        schema=vol.Schema(
            {
                vol.Required("task_name"): cv.string,
                vol.Optional("entity_id"): cv.entity_id,
                vol.Required("instructions"): cv.string,
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


async def async_service_generate_text(call: ServiceCall) -> ServiceResponse:
    """Run the run task service."""
    result = await async_generate_text(hass=call.hass, **call.data)
    return result.as_dict()  # type: ignore[return-value]


class AITaskPreferences:
    """AI Task preferences."""

    KEYS = ("gen_text_entity_id",)

    gen_text_entity_id: str | None = None

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
            setattr(self, key, data[key])

    @callback
    def async_set_preferences(
        self,
        *,
        gen_text_entity_id: str | None | UndefinedType = UNDEFINED,
    ) -> None:
        """Set the preferences."""
        changed = False
        for key, value in (("gen_text_entity_id", gen_text_entity_id),):
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
