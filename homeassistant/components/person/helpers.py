"""Helpers for the person integration."""

import logging

from homeassistant.components import persistent_notification
from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import CONF_USER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def filter_yaml_data(hass: HomeAssistant, persons: list[dict]) -> list[dict]:
    """Validate YAML data that we can't validate via schema."""
    filtered = []
    person_invalid_user = []

    for person_conf in persons:
        user_id = person_conf.get(CONF_USER_ID)

        if user_id is not None and await hass.auth.async_get_user(user_id) is None:
            _LOGGER.error(
                "Invalid user_id detected for person %s",
                person_conf[CONF_ID],
            )
            person_invalid_user.append(
                f"- Person {person_conf[CONF_NAME]} (id: {person_conf[CONF_ID]}) points"
                f" at invalid user {user_id}"
            )
            continue

        filtered.append(person_conf)

    if person_invalid_user:
        persistent_notification.async_create(
            hass,
            f"""
The following persons point at invalid users:

{"- ".join(person_invalid_user)}
            """,
            "Invalid Person Configuration",
            DOMAIN,
        )

    return filtered
