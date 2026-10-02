"""Diagnostics support for Mistral AI."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_PROMPT
from homeassistant.helpers import entity_registry as er

from .api import model_status_from_list
from .const import CONF_CHAT_MODEL, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import MistralAIConfigEntry

TO_REDACT = {
    CONF_API_KEY,
    CONF_PROMPT,
}


def _get_model_status(entry: MistralAIConfigEntry, model_id: str) -> dict[str, Any]:
    """Fetch the deprecation status of a model for diagnostics."""
    client = entry.runtime_data.client
    try:
        models = client.models.list(timeout_ms=10_000).data or []
    except Exception as err:  # noqa: BLE001
        LOGGER.warning("Error fetching models for diagnostics: %s", err)
        return {"error": str(err)}

    return model_status_from_list(models, model_id)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MistralAIConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    subentries: dict[str, Any] = {}
    for subentry in entry.subentries.values():
        data = dict(subentry.data)
        model_id = data.get(CONF_CHAT_MODEL)

        subentry_info: dict[str, Any] = {
            "title": subentry.title,
            "subentry_type": subentry.subentry_type,
            "data": async_redact_data(data, TO_REDACT),
        }

        if model_id:
            subentry_info["model"] = await hass.async_add_executor_job(
                _get_model_status, entry, model_id
            )

        subentries[subentry.subentry_id] = subentry_info

    return {
        "title": entry.title,
        "entry_id": entry.entry_id,
        "entry_version": f"{entry.version}.{entry.minor_version}",
        "state": entry.state.value,
        "data": async_redact_data(entry.data, TO_REDACT),
        "subentries": subentries,
        "entities": {
            entity_entry.entity_id: entity_entry.extended_dict
            for entity_entry in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
        },
    }
