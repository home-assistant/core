"""Integration to offer AI tasks to Home Assistant."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
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

from .const import (
    ATTR_INSTRUCTIONS,
    ATTR_TASK_NAME,
    DATA_COMPONENT,
    DATA_PREFERENCES,
    DOMAIN,
    SERVICE_GENERATE_DATA,
    AITaskEntityFeature,
)
from .entity import AITaskEntity
from .http import async_setup as async_setup_http
from .task import GenDataTask, GenDataTaskResult, async_generate_data

__all__ = [
    "DOMAIN",
    "AITaskEntity",
    "AITaskEntityFeature",
    "GenDataTask",
    "GenDataTaskResult",
    "async_generate_data",
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
    async_setup_http(hass)
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_DATA,
        async_service_generate_data,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TASK_NAME): cv.string,
                vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
                vol.Required(ATTR_INSTRUCTIONS): cv.string,
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
    """Run the run task service."""
    result = await async_generate_data(hass=call.hass, **call.data)
    return result.as_dict()


class AITaskPreferences:
    """AI Task preferences."""

    KEYS = ("gen_data_entity_id",)

    gen_data_entity_id: str | None = None

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
        gen_data_entity_id: str | None | UndefinedType = UNDEFINED,
    ) -> None:
        """Set the preferences."""
        changed = False
        for key, value in (("gen_data_entity_id", gen_data_entity_id),):
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
