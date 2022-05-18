"""outsourced from entity to resolve circurlar imports issue."""
from __future__ import annotations

from collections.abc import Iterable

from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import ensure_unique_string, slugify


@callback
def async_generate_entity_id(
    entity_id_format: str,
    name: str | None,
    current_ids: Iterable[str] | None = None,
    hass: HomeAssistant | None = None,
) -> str:
    """Generate a unique entity ID based on given entity IDs or used IDs."""
    name = (name or DEVICE_DEFAULT_NAME).lower()
    preferred_string = entity_id_format.format(slugify(name))

    if current_ids is not None:
        return ensure_unique_string(preferred_string, current_ids)

    if hass is None:
        raise ValueError("Missing required parameter current_ids or hass")

    test_string = preferred_string
    tries = 1
    while not hass.states.async_available(test_string):
        tries += 1
        test_string = f"{preferred_string}_{tries}"

    return test_string
