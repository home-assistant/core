"""API endpoint management for the VegeHub integration."""

import logging

from homeassistant.components import http
from homeassistant.core import HomeAssistant

from .const import API_PATH, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant) -> bool:
    """Set up the HTTP endpoint for VegeHub data."""

    class VegeHubView(http.HomeAssistantView):
        """Test the HTTP views."""

        name = "api:vegehub:update"
        url = API_PATH
        method = "post"
        requires_auth = False

        async def post(self, request):
            """Handle POST requests and process the JSON data."""
            # try:
            data = await request.json()
            incoming_key = data.get("api_key")

            # Process sensor data like before
            if "sensors" in data:
                for sensor in data["sensors"]:
                    slot = sensor.get("slot")
                    latest_sample = sensor["samples"][-1]
                    timestamp = latest_sample["t"]
                    value = latest_sample["v"]

                    # Use the slot number as part of the entity ID
                    entity_id = f"vegehub_{incoming_key}_{slot}".lower()

                    _LOGGER.info(
                        "Received sensor data - Slot: %s, Value: %s, Time: %s",
                        slot,
                        value,
                        timestamp,
                    )

                    # Update Home Assistant entity with the new sensor data
                    await self._update_sensor_entity(hass, value, entity_id)

            return self.json({"status": "ok"})
            # except Exception as e:
            #     _LOGGER.error(f"Error processing POST request: {e}")
            #     return self.json({"status": "error", "message": str(e)})

        async def _update_sensor_entity(
            self, hass: HomeAssistant, value: float, entity_id: str
        ):
            """Update the corresponding Home Assistant entity with the latest sensor value."""

            # Find the sensor entity and update its state
            entity = None
            try:
                if entity_id in hass.data[DOMAIN]:
                    entity = hass.data[DOMAIN][entity_id]
                if not entity:
                    _LOGGER.error("Sensor entity %s not found", entity_id)
                else:
                    await entity.async_update_sensor(value)
                # _LOGGER.info(f"Updated entity {entity_id} with value: {value}")
            except Exception as e:
                _LOGGER.error("Sensor entity %s not found:%s", entity_id, e)
                raise

    _LOGGER.info("Registering api endpoint view at %s", API_PATH)
    # Register the route with Home Assistant
    hass.http.register_view(VegeHubView)

    return True
