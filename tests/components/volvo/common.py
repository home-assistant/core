"""Common test utils for Volvo."""

from volvocarsapi.models import VolvoCarsValueField

from homeassistant.components.volvo.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonObjectType, json_loads_object

from tests.common import async_load_fixture

_MODEL_SPECIFIC_RESPONSES = {
    "ex30_2024": ["vehicle"],
    "ex30_2024_no_colour": ["vehicle"],
    "s90_diesel_2018": ["diagnostics", "statistics", "vehicle"],
    "xc40_electric_2024": ["vehicle"],
    "xc90_petrol_2019": ["commands", "vehicle"],
}


async def async_load_fixture_as_json(
    hass: HomeAssistant, name: str, model: str
) -> JsonObjectType:
    """Load a JSON object from a fixture."""
    if name in _MODEL_SPECIFIC_RESPONSES[model]:
        name = f"{model}/{name}"

    fixture = await async_load_fixture(hass, f"{name}.json", DOMAIN)
    return json_loads_object(fixture)


async def async_load_fixture_as_value_field(
    hass: HomeAssistant, name: str, model: str
) -> dict[str, VolvoCarsValueField]:
    """Load a `VolvoCarsValueField` object from a fixture."""
    data = await async_load_fixture_as_json(hass, name, model)
    return {key: VolvoCarsValueField.from_dict(value) for key, value in data.items()}
