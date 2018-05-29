"""HTTP views to interact with the entity registry."""
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.helpers.entity_registry import async_get_registry


async def async_setup(hass):
    """Enable the Entity Registry views."""
    hass.http.register_view(ConfigManagerEntityView)
    return True


class ConfigManagerEntityView(HomeAssistantView):
    """View to interact with an entity registry entry."""

    url = '/api/config/entity_registry/{entity_id}'
    name = 'api:config:entity_registry:entity'

    async def get(self, request, entity_id):
        """Get the entity registry settings for an entity."""
        hass = request.app['hass']
        registry = await async_get_registry(hass)
        entry = registry.entities.get(entity_id)

        if entry is None:
            return self.json_message('Entry not found', 404)

        return self.json(_entry_dict(entry))

    @RequestDataValidator(vol.Schema({
        # If passed in, we update value. Passing None will remove old value.
        vol.Optional('name'): vol.Any(str, None),
    }))
    async def post(self, request, entity_id, data):
        """Update the entity registry settings for an entity."""
        hass = request.app['hass']
        registry = await async_get_registry(hass)

        if entity_id not in registry.entities:
            return self.json_message('Entry not found', 404)

        entry = registry.async_update_entity(entity_id, **data)
        return self.json(_entry_dict(entry))


@callback
def _entry_dict(entry):
    """Helper to convert entry to API format."""
    return {
        'entity_id': entry.entity_id,
        'name': entry.name
    }
