"""Set up the demo environment that mimics interaction with devices."""
from __future__ import annotations

import asyncio
import datetime
from random import random

from homeassistant import config_entries, setup
from homeassistant.components import persistent_notification
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
    EVENT_HOMEASSISTANT_START,
    SOUND_PRESSURE_DB,
    TEMP_CELSIUS,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
    Platform,
)
import homeassistant.core as ha
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

DOMAIN = "demo"

COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM = [
    Platform.AIR_QUALITY,
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.VACUUM,
    Platform.WATER_HEATER,
]

COMPONENTS_WITH_DEMO_PLATFORM = [
    Platform.TTS,
    Platform.STT,
    Platform.MAILBOX,
    Platform.NOTIFY,
    Platform.IMAGE_PROCESSING,
    Platform.CALENDAR,
    Platform.DEVICE_TRACKER,
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

    async def demo_start_listener(_event: Event) -> None:
        """Finish set up."""
        await finish_setup(hass, config)

    hass.bus.async_listen(EVENT_HOMEASSISTANT_START, demo_start_listener)

    # Create issues
    async_create_issue(
        hass,
        DOMAIN,
        "transmogrifier_deprecated",
        breaks_in_ha_version="2023.1.1",
        is_fixable=False,
        learn_more_url="https://en.wiktionary.org/wiki/transmogrifier",
        severity=IssueSeverity.WARNING,
        translation_key="transmogrifier_deprecated",
    )

    async_create_issue(
        hass,
        DOMAIN,
        "out_of_blinker_fluid",
        breaks_in_ha_version="2023.1.1",
        is_fixable=True,
        learn_more_url="https://www.youtube.com/watch?v=b9rntRxLlbU",
        severity=IssueSeverity.CRITICAL,
        translation_key="out_of_blinker_fluid",
    )

    async_create_issue(
        hass,
        DOMAIN,
        "unfixable_problem",
        is_fixable=False,
        learn_more_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        severity=IssueSeverity.WARNING,
        translation_key="unfixable_problem",
    )

    async_create_issue(
        hass,
        DOMAIN,
        "bad_psu",
        is_fixable=True,
        learn_more_url="https://www.youtube.com/watch?v=b9rntRxLlbU",
        severity=IssueSeverity.CRITICAL,
        translation_key="bad_psu",
    )

    return True


def _generate_mean_statistics(
    start: datetime.datetime, end: datetime.datetime, init_value: float, max_diff: float
) -> list[StatisticData]:
    statistics: list[StatisticData] = []
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


async def _insert_sum_statistics(
    hass: HomeAssistant,
    metadata: StatisticMetaData,
    start: datetime.datetime,
    end: datetime.datetime,
    max_diff: float,
) -> None:
    statistics: list[StatisticData] = []
    now = start
    sum_ = 0.0
    statistic_id = metadata["statistic_id"]

    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, False
    )
    if statistic_id in last_stats:
        sum_ = last_stats[statistic_id][0]["sum"] or 0
    while now < end:
        sum_ = sum_ + random() * max_diff
        statistics.append(
            {
                "start": now,
                "sum": sum_,
            }
        )
        now = now + datetime.timedelta(hours=1)

    async_add_external_statistics(hass, metadata, statistics)


async def _insert_statistics(hass: HomeAssistant) -> None:
    """Insert some fake statistics."""
    now = dt_util.now()
    yesterday = now - datetime.timedelta(days=1)
    yesterday_midnight = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    today_midnight = yesterday_midnight + datetime.timedelta(days=1)

    # Fake yesterday's temperatures
    metadata: StatisticMetaData = {
        "source": DOMAIN,
        "name": "Outdoor temperature",
        "statistic_id": f"{DOMAIN}:temperature_outdoor",
        "unit_of_measurement": TEMP_CELSIUS,
        "has_mean": True,
        "has_sum": False,
    }
    statistics = _generate_mean_statistics(yesterday_midnight, today_midnight, 15, 1)
    async_add_external_statistics(hass, metadata, statistics)

    # Add external energy consumption in kWh, ~ 12 kWh / day
    # This should be possible to pick for the energy dashboard
    metadata = {
        "source": DOMAIN,
        "name": "Energy consumption 1",
        "statistic_id": f"{DOMAIN}:energy_consumption_kwh",
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "has_mean": False,
        "has_sum": True,
    }
    await _insert_sum_statistics(hass, metadata, yesterday_midnight, today_midnight, 1)

    # Add external energy consumption in MWh, ~ 12 kWh / day
    # This should not be possible to pick for the energy dashboard
    metadata = {
        "source": DOMAIN,
        "name": "Energy consumption 2",
        "statistic_id": f"{DOMAIN}:energy_consumption_mwh",
        "unit_of_measurement": ENERGY_MEGA_WATT_HOUR,
        "has_mean": False,
        "has_sum": True,
    }
    await _insert_sum_statistics(
        hass, metadata, yesterday_midnight, today_midnight, 0.001
    )

    # Add external gas consumption in m³, ~6 m3/day
    # This should be possible to pick for the energy dashboard
    metadata = {
        "source": DOMAIN,
        "name": "Gas consumption 1",
        "statistic_id": f"{DOMAIN}:gas_consumption_m3",
        "unit_of_measurement": VOLUME_CUBIC_METERS,
        "has_mean": False,
        "has_sum": True,
    }
    await _insert_sum_statistics(
        hass, metadata, yesterday_midnight, today_midnight, 0.5
    )

    # Add external gas consumption in ft³, ~180 ft3/day
    # This should not be possible to pick for the energy dashboard
    metadata = {
        "source": DOMAIN,
        "name": "Gas consumption 2",
        "statistic_id": f"{DOMAIN}:gas_consumption_ft3",
        "unit_of_measurement": VOLUME_CUBIC_FEET,
        "has_mean": False,
        "has_sum": True,
    }
    await _insert_sum_statistics(hass, metadata, yesterday_midnight, today_midnight, 15)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set the config entry up."""
    # Set up demo platforms with config entry
    await hass.config_entries.async_forward_entry_setups(
        config_entry, COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM
    )
    if "recorder" in hass.config.components:
        await _insert_statistics(hass)
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
