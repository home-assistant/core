"""Support for LLM Google travel time tool use."""

import logging

from googlemaps import Client
from googlemaps.exceptions import ApiError, HTTPError, Timeout, TransportError
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

_LOGGER = logging.getLogger(__name__)


class GoogleMapsTravelTimeTool(llm.Tool):
    """Representation of a Google travel LLM tool."""

    name = "GetTravelTimeFromGoogleMaps"
    description = "Returns the travel time and itinerary from Google Maps based on origin and destination."
    parameters = vol.Schema(
        {
            vol.Required("origin", description="Origin address or station"): str,
            vol.Required(
                "destination", description="Destination address or station"
            ): str,
            vol.Required("mode", default="driving"): vol.In(
                ["driving", "walking", "bicycling", "transit"]
            ),
            vol.Optional(
                "departure_time",
                description="Departure time. Takes current time if not present.",
            ): vol.Datetime(),
            vol.Required(
                "only_time",
                description="Only return the travel time",
                default=False,
            ): vol.Boolean(),
        }
    )

    def __init__(self, client: Client) -> None:
        """Initialize the tool."""
        self._client = client

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Perform the asynchronous call to the Google travel LLM tool."""
        # check if tool input follows the schema
        origin = tool_input.tool_args["origin"]
        destination = tool_input.tool_args["destination"]
        mode = tool_input.tool_args.get("mode", "driving")
        if "departure_time" in tool_input.tool_args:
            departure_time = dt_util.parse_datetime(
                tool_input.tool_args["departure_time"]
            )
        else:
            departure_time = None
        only_time = tool_input.tool_args.get("only_time", False)

        def call_directions():
            return self._client.directions(
                origin,
                destination,
                mode=mode,
                departure_time=departure_time,
            )

        try:
            directions_result = await hass.async_add_executor_job(call_directions)
        except (ApiError, HTTPError, Timeout, TransportError) as error:
            _LOGGER.error("Error getting directions from Google Maps: %s", error)
            return {
                "error": f"Error getting directions from Google Maps. Error details: {error}"
            }
        if only_time:
            try:
                return {
                    "travel_time": directions_result[0]["legs"][0]["duration"]["text"]
                }
            except KeyError as error:
                _LOGGER.error("Error getting travel time from Google Maps: %s", error)
                return directions_result

        return directions_result


class GoogleMapsTravelTimeAPI(llm.API):
    """Google Maps Travel Time API for LLMs."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        """Initialize the API."""
        super().__init__(
            hass=hass,
            id="google_travel_time",
            name="Google Travel Time API",
        )
        self._client = Client(api_key, timeout=10)

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        return llm.APIInstance(
            api=self,
            api_prompt="Call the tools to get travel time and itinerary from Google Maps.",
            llm_context=llm_context,
            tools=[GoogleMapsTravelTimeTool(client=self._client)],
        )
