"""Set up the demo environment that mimics interaction with devices."""
from __future__ import annotations

import asyncio

from homeassistant import config_entries, setup
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_START,
    Platform,
    UnitOfSoundPressure,
)
import homeassistant.core as ha
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

DOMAIN = "demo"

COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM = [
    Platform.AIR_QUALITY,
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.DATE,
    Platform.DATETIME,
    Platform.EVENT,
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.STT,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.TIME,
    Platform.UPDATE,
    Platform.VACUUM,
    Platform.WATER_HEATER,
]

COMPONENTS_WITH_DEMO_PLATFORM = [
    Platform.TTS,
    Platform.MAILBOX,
    Platform.NOTIFY,
    Platform.IMAGE_PROCESSING,
    Platform.CALENDAR,
    Platform.DEVICE_TRACKER,
    Platform.WEATHER,
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the demo environment."""
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
            )
        )

    if DOMAIN not in config:
        return True

    # Set up demo platforms
    for platform in COMPONENTS_WITH_DEMO_PLATFORM:
        hass.async_create_task(async_load_platform(hass, platform, DOMAIN, {}, config))

    config.setdefault(ha.DOMAIN, {})
    config.setdefault(DOMAIN, {})

    # Set up sun
    if not hass.config.latitude:
        hass.config.latitude = 32.87336

    if not hass.config.longitude:
        hass.config.longitude = 117.22743

    tasks = [setup.async_setup_component(hass, "sun", config)]

    # Set up input select
    tasks.append(
        setup.async_setup_component(
            hass,
            "input_select",
            {
                "input_select": {
                    "living_room_preset": {
                        "options": ["Visitors", "Visitors with kids", "Home Alone"]
                    },
                    "who_cooks": {
                        "icon": "mdi:panda",
                        "initial": "Anne Therese",
                        "name": "Cook today",
                        "options": ["Paulus", "Anne Therese"],
                    },
                }
            },
        )
    )

    # Set up input boolean
    tasks.append(
        setup.async_setup_component(
            hass,
            "input_boolean",
            {
                "input_boolean": {
                    "notify": {
                        "icon": "mdi:car",
                        "initial": False,
                        "name": "Notify Anne Therese is home",
                    }
                }
            },
        )
    )

    # Set up input button
    tasks.append(
        setup.async_setup_component(
            hass,
            "input_button",
            {
                "input_button": {
                    "bell": {
                        "icon": "mdi:bell-ring-outline",
                        "name": "Ring bell",
                    }
                }
            },
        )
    )

    # Set up input number
    tasks.append(
        setup.async_setup_component(
            hass,
            "input_number",
            {
                "input_number": {
                    "noise_allowance": {
                        "icon": "mdi:bell-ring",
                        "min": 0,
                        "max": 10,
                        "name": "Allowed Noise",
                        "unit_of_measurement": UnitOfSoundPressure.DECIBEL,
                    }
                }
            },
        )
    )

    results = await asyncio.gather(*tasks)

    if any(not result for result in results):
        return False

    # Set up example persistent notification
    persistent_notification.async_create(
        hass,
        "This is an example of a persistent notification.",
        title="Example Notification",
    )

    async def demo_start_listener(_event: Event) -> None:
        """Finish set up."""
        await finish_setup(hass, config)

    hass.bus.async_listen(EVENT_HOMEASSISTANT_START, demo_start_listener)

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set the config entry up."""
    # Set up demo platforms with config entry
    await hass.config_entries.async_forward_entry_setups(
        config_entry, COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM
    )
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(
        config_entry, COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM
    )
    return True


async def finish_setup(hass: HomeAssistant, config: ConfigType) -> None:
    """Finish set up once demo platforms are set up."""
    switches: list[str] | None = None
    lights: list[str] | None = None

    while not switches and not lights:
        # Not all platforms might be loaded.
        if switches is not None:
            await asyncio.sleep(0)
        switches = sorted(hass.states.async_entity_ids("switch"))
        lights = sorted(hass.states.async_entity_ids("light"))

    assert switches is not None
    assert lights is not None
    # Set up scripts
    await setup.async_setup_component(
        hass,
        "script",
        {
            "script": {
                "demo": {
                    "alias": f"Toggle {lights[0].split('.')[1]}",
                    "sequence": [
                        {
                            "service": "light.turn_off",
                            "data": {ATTR_ENTITY_ID: lights[0]},
                        },
                        {"delay": {"seconds": 5}},
                        {
                            "service": "light.turn_on",
                            "data": {ATTR_ENTITY_ID: lights[0]},
                        },
                        {"delay": {"seconds": 5}},
                        {
                            "service": "light.turn_off",
                            "data": {ATTR_ENTITY_ID: lights[0]},
                        },
                    ],
                }
            }
        },
    )

    # Set up scenes
    await setup.async_setup_component(
        hass,
        "scene",
        {
            "scene": [
                {
                    "name": "Romantic lights",
                    "entities": {
                        lights[0]: True,
                        lights[1]: {
                            "state": "on",
                            "xy_color": [0.33, 0.66],
                            "brightness": 200,
                        },
                    },
                },
                {
                    "name": "Switch on and off",
                    "entities": {switches[0]: True, switches[1]: False},
                },
            ]
        },
    )
