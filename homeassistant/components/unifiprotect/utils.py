"""UniFi Protect Integration utils."""
from __future__ import annotations

import asyncio
from enum import Enum
from io import StringIO
import json
import logging
from pathlib import Path
import shutil
import time
from typing import Any

from pyunifiprotect.api import ProtectApiClient
from pyunifiprotect.test_util import SampleDataGenerator
from pyunifiprotect.utils import print_ws_stat_summary

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntry

_LOGGER = logging.getLogger(__name__)


def get_nested_attr(obj: Any, attr: str) -> Any:
    """Fetch a nested attribute."""
    attrs = attr.split(".")

    value = obj
    for key in attrs:
        if not hasattr(value, key):
            return None
        value = getattr(value, key)

    if isinstance(value, Enum):
        value = value.value

    return value


async def profile_ws_messages(
    hass: HomeAssistant,
    protect: ProtectApiClient,
    seconds: int,
    device_entry: DeviceEntry,
) -> None:
    """Profile the websocket."""
    if protect.bootstrap.capture_ws_stats:
        raise HomeAssistantError("Profile already in progress")

    protect.bootstrap.capture_ws_stats = True

    start_time = time.time()
    name = device_entry.name_by_user or device_entry.name or device_entry.id
    nvr_id = name.replace(" ", "_").lower()
    message_id = f"ufp_ws_profiler_{nvr_id}_{start_time}"
    hass.components.persistent_notification.async_create(
        "The WS profile has started. This notification will be updated when it is complete.",
        title=f"{name}: WS Profile Started",
        notification_id=message_id,
    )
    _LOGGER.info("%s: Start WS Profile for %ss", name, seconds)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        await asyncio.sleep(10)

    protect.bootstrap.capture_ws_stats = False

    json_data = [s.__dict__ for s in protect.bootstrap.ws_stats]
    out_path = hass.config.path(f"ufp_ws_profile.{start_time}.json")
    with open(out_path, "w", encoding="utf8") as outfile:
        json.dump(json_data, outfile, indent=4)

    stats_buffer = StringIO()
    print_ws_stat_summary(protect.bootstrap.ws_stats, output=stats_buffer.write)
    protect.bootstrap.clear_ws_stats()
    _LOGGER.info("%s: Complete WS Profile:\n%s", name, stats_buffer.getvalue())

    hass.components.persistent_notification.async_create(
        f"Wrote raw stats to {out_path}\n\n```\n{stats_buffer.getvalue()}\n```",
        title=f"{name}: WS Profile Completed",
        notification_id=message_id,
    )


async def generate_sample_data(
    hass: HomeAssistant,
    protect: ProtectApiClient,
    seconds: int,
    anonymize: bool,
    device_entry: DeviceEntry,
) -> None:
    """Generate sample data from Protect instance."""

    start_time = time.time()
    name = device_entry.name_by_user or device_entry.name or device_entry.id
    folder = f"ufp_sample.{start_time}"
    out_path = hass.config.path(folder)
    nvr_id = name.replace(" ", "_").lower()
    message_id = f"ufp_ws_profiler_{nvr_id}_{start_time}"
    hass.components.persistent_notification.async_create(
        "The sample data generation has started. This notification will be updated when it is complete.",
        title=f"{name}: Sample Data Generation Started",
        notification_id=message_id,
    )

    _LOGGER.info(
        "%s: Start Sample Data for %ss (anonymize: %s)", name, seconds, anonymize
    )
    await SampleDataGenerator(
        protect, Path(out_path), anonymize, seconds
    ).async_generate(close_session=False)
    shutil.make_archive(out_path, "zip", out_path)
    shutil.rmtree(out_path)
    out_path = f"{out_path}.zip"

    _LOGGER.info("%s: Complete Sample Data:\n%s", name, out_path)

    hass.components.persistent_notification.async_create(
        f"Wrote sample data to {out_path}",
        title=f"{name}: Sample Data Generation Completed",
        notification_id=message_id,
    )
