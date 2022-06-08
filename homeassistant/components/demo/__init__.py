"""Set up the demo environment that mimics interaction with devices."""
import asyncio
import datetime
from random import random

from homeassistant import config_entries, setup
from homeassistant.components import persistent_notification
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_START,
    SOUND_PRESSURE_DB,
)
import homeassistant.core as ha
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

DOMAIN = "demo"

COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM = [
    "air_quality",
    "alarm_control_panel",
    "binary_sensor",
    "button",
    "camera",
    "climate",
    "cover",
    "fan",
    "humidifier",
    "light",
    "lock",
    "media_player",
    "number",
    "select",
    "sensor",
    "siren",
    "switch",
    "update",
    "vacuum",
    "water_heater",
]

COMPONENTS_WITH_DEMO_PLATFORM = [
    "tts",
    "stt",
    "mailbox",
    "notify",
    "image_processing",
    "calendar",
    "device_tracker",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the demo environment."""
    if DOMAIN not in config:
        return True

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
            )
        )

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
                        "unit_of_measurement": SOUND_PRESSURE_DB,
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

    async def demo_start_listener(_event):
        """Finish set up."""
        await finish_setup(hass, config)

    hass.bus.async_listen(EVENT_HOMEASSISTANT_START, demo_start_listener)

    return True


def _generate_mean_statistics(start, end, init_value, max_diff):
    statistics = []
    mean = init_value
    now = start
    while now < end:
        mean = mean + random() * max_diff - max_diff / 2
        statistics.append(
            {
                "start": now,
                "mean": mean,
                "min": mean - random() * max_diff,
                "max": mean + random() * max_diff,
            }
        )
        now = now + datetime.timedelta(hours=1)

    return statistics


def _generate_sum_statistics(start, end, init_value, max_diff):
    statistics = []
    now = start
    sum_ = init_value
    while now < end:
        sum_ = sum_ + random() * max_diff
        statistics.append(
            {
                "start": now,
                "sum": sum_,
            }
        )
        now = now + datetime.timedelta(hours=1)

    return statistics


async def _insert_statistics(hass):
    """Insert some fake statistics."""
    now = dt_util.now()
    yesterday = now - datetime.timedelta(days=1)
    yesterday_midnight = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

    # Fake yesterday's temperatures
    metadata = {
        "source": DOMAIN,
        "statistic_id": f"{DOMAIN}:temperature_outdoor",
        "unit_of_measurement": "°C",
        "has_mean": True,
        "has_sum": False,
    }
    statistics = _generate_mean_statistics(
        yesterday_midnight, yesterday_midnight + datetime.timedelta(days=1), 15, 1
    )
    async_add_external_statistics(hass, metadata, statistics)

    # Fake yesterday's energy consumption
    metadata = {
        "source": DOMAIN,
        "statistic_id": f"{DOMAIN}:energy_consumption",
        "unit_of_measurement": "kWh",
        "has_mean": False,
        "has_sum": True,
    }
    statistic_id = f"{DOMAIN}:energy_consumption"
    sum_ = 0
    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True
    )
    if "domain:energy_consumption" in last_stats:
        sum_ = last_stats["domain.electricity_total"]["sum"] or 0
    statistics = _generate_sum_statistics(
        yesterday_midnight, yesterday_midnight + datetime.timedelta(days=1), sum_, 1
    )
    async_add_external_statistics(hass, metadata, statistics)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set the config entry up."""
    # Set up demo platforms with config entry
    for platform in COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )
    if "recorder" in hass.config.components:
        await _insert_statistics(hass)
    return True


async def finish_setup(hass, config):
    """Finish set up once demo platforms are set up."""
    switches = None
    lights = None

    while not switches and not lights:
        # Not all platforms might be loaded.
        if switches is not None:
            await asyncio.sleep(0)
        switches = sorted(hass.states.async_entity_ids("switch"))
        lights = sorted(hass.states.async_entity_ids("light"))

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
