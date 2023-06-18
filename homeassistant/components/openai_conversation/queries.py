"""OpenAI callable query functions."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template


class Queries:
    """Queries exectutable against hass."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.functions = [
            {
                "name": "query_all_entities",
                "description": "Query to get all device entities that can be controlled and their current state",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "query_weather_report",
                "description": "Query the current weather for a specified location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity": {
                            "type": "string",
                            "description": "ID of the entity to query without the weather prefix",
                        },
                    },
                    "required": ["entity"],
                },
            },
        ]

    async def query_all_entities(self):
        """Get all device entities that can be controlled and their current state."""
        return template.Template(
            """
            An overview of the areas and the devices in this smart home:
            {%- for area in areas() %}
            {%- set area_info = namespace(printed=false) %}
            {%- for device in area_devices(area) -%}
                {%- if not device_attr(device, "disabled_by") and not device_attr(device, "entry_type") and device_attr(device, "name") %}
                {%- if not area_info.printed %}

            {{ area_name(area) }}:
                    {%- set area_info.printed = true %}
                {%- endif %}
            - {{device_entities(device)}}
                {%- endif %}
            {%- endfor %}
            {%- endfor %}
            """,
            self.hass,
        ).async_render(
            {
                "ha_name": self.hass.config.location_name,
            },
            parse_result=False,
        )

    async def query_weather_report(self):
        """Query the current weather for a specified location."""
        return template.Template(
            """
            {% set weather = states('weather.forecast_home') %}
            {% set forecast = state_attr('weather.forecast_home', 'forecast') %}
            {% set current_rain_chance = state_attr('weather.forecast_home', 'precipitation_probability') %}
            {% set current_rain_unit = state_attr('weather.forecast_home', 'precipitation_unit') %}
            {% set current_rain = state_attr('weather.forecast_home', 'rain') %}

            The current weather is {{ weather }} with a temperature of {{ state_attr('weather.forecast_home', 'temperature') }}°F{% if current_rain %} and {{ current_rain }}{{ current_rain_unit }} of rain{% endif %}.

            Forecast for the next three days:
            {% for day in forecast[:3] %}
            - {{ day.datetime }}: {{ day.condition }} with a high of {{ day.temperature }}°F and a low of {{ day.templow }}°F{% if day.precipitation %} and {{ day.precipitation }}% chance of rain{% endif %}.
            {% endfor %}
            """,
            self.hass,
        ).async_render(
            {
                "ha_name": self.hass.config.location_name,
            },
            parse_result=False,
        )
