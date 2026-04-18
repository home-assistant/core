"""Test for the Schedule integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from homeassistant.components.schedule import STORAGE_VERSION, STORAGE_VERSION_MINOR
from homeassistant.components.schedule.const import (
    CONF_DATA,
    CONF_FRIDAY,
    CONF_FROM,
    CONF_MONDAY,
    CONF_SATURDAY,
    CONF_SUNDAY,
    CONF_THURSDAY,
    CONF_TO,
    CONF_TUESDAY,
    CONF_WEDNESDAY,
    DOMAIN,
)
from homeassistant.const import CONF_ICON, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def schedule_setup(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> Callable[..., Coroutine[Any, Any, bool]]:
    """Schedule setup."""

    async def _schedule_setup(
        items: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> bool:
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": STORAGE_VERSION,
                "minor_version": STORAGE_VERSION_MINOR,
                "data": {
                    "items": [
                        {
                            CONF_ID: "from_storage",
                            CONF_NAME: "from storage",
                            CONF_ICON: "mdi:party-popper",
                            CONF_FRIDAY: [
                                {
                                    CONF_FROM: "17:00:00",
                                    CONF_TO: "23:59:59",
                                    CONF_DATA: {"party_level": "epic"},
                                },
                            ],
                            CONF_SATURDAY: [
                                {CONF_FROM: "00:00:00", CONF_TO: "23:59:59"},
                            ],
                            CONF_SUNDAY: [
                                {
                                    CONF_FROM: "00:00:00",
                                    CONF_TO: "24:00:00",
                                    CONF_DATA: {"entry": "VIPs only"},
                                },
                            ],
                        }
                    ]
                },
            }
        else:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "minor_version": STORAGE_VERSION_MINOR,
                "data": {"items": items},
            }
        if config is None:
            config = {
                DOMAIN: {
                    "from_yaml": {
                        CONF_NAME: "from yaml",
                        CONF_ICON: "mdi:party-pooper",
                        CONF_MONDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_TUESDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_WEDNESDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_THURSDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_FRIDAY: [
                            {
                                CONF_FROM: "00:00:00",
                                CONF_TO: "23:59:59",
                                CONF_DATA: {"party_level": "epic"},
                            }
                        ],
                        CONF_SATURDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_SUNDAY: [
                            {
                                CONF_FROM: "00:00:00",
                                CONF_TO: "23:59:59",
                                CONF_DATA: {"entry": "VIPs only"},
                            }
                        ],
                    }
                }
            }
        return await async_setup_component(hass, DOMAIN, config)

    return _schedule_setup
