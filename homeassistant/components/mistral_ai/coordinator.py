"""Coordinator for the Mistral AI models list."""

from datetime import timedelta
from typing import TYPE_CHECKING, Any, override

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import CAPABILITY_BY_TYPE, fetch_models, model_status_from_list
from .const import LOGGER

if TYPE_CHECKING:
    from . import MistralAIConfigEntry

UPDATE_INTERVAL = timedelta(hours=12)


class MistralModelsCoordinator(DataUpdateCoordinator[list[Any]]):
    """Coordinator fetching the full model list once, shared by all entities."""

    def __init__(
        self, hass: HomeAssistant, entry: MistralAIConfigEntry, client: Any
    ) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self._client = client
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=UPDATE_INTERVAL,
        )

    @property
    def client(self) -> Any:
        """Return the Mistral client."""
        return self._client

    @override
    async def _async_update_data(self) -> list[Any]:
        """Fetch the list of models from the Mistral API."""
        return await self.hass.async_add_executor_job(fetch_models, self._client)

    def model_ids(self, subentry_type: str) -> list[str]:
        """Return the model IDs available for a subentry type."""
        capability = CAPABILITY_BY_TYPE.get(subentry_type)
        if capability is None or self.data is None:
            return []
        return sorted(
            model.id
            for model in self.data
            if getattr(getattr(model, "capabilities", None), capability, False)
        )

    def model_status(self, model_id: str) -> dict[str, Any]:
        """Return the deprecation status of a model."""
        if self.data is None:
            return {"id": model_id, "status": "unknown"}
        return model_status_from_list(self.data, model_id)
