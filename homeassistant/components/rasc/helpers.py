"""RASC integration helpers."""
from __future__ import annotations

import csv
from enum import Enum
import json
import logging
from logging import Logger
import math
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, ATTR_SERVICE, RASC_RESPONSE
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def fire(
    hass: HomeAssistant,
    rasc_type: str,
    entity_id: str,
    action: str,
    logger: Logger | None = None,
    service_data: dict[str, Any] | None = None,
):
    """Fire rasc response."""
    if logger:
        logger.info("%s %s: %s", entity_id, action, rasc_type)
    service_data = service_data or {}
    hass.bus.async_fire(
        RASC_RESPONSE,
        {
            "type": rasc_type,
            ATTR_SERVICE: action,
            ATTR_ENTITY_ID: entity_id,
            **{
                str(key): value
                for key, value in service_data.items()
                if key != ATTR_ENTITY_ID
            },
        },
    )


class Dataset(Enum):
    """Dataset enum."""

    THERMOSTAT = "thermostat"
    DOOR = "door"
    ELEVATOR = "elevator"
    PROJECTOR = "projector"
    SHADE = "shade"


def load_dataset(name: Dataset, action: str | None = None):
    """Load dataset."""
    if name.value == "thermostat":
        dataset = _get_thermo_datasets()
    else:
        with open(
            f"homeassistant/components/rasc/datasets/{name.value}.json",
            encoding="utf-8",
        ) as f:
            dataset = json.load(f)

    if action is None:
        return dataset

    if action not in dataset:
        _LOGGER.info(
            "Action not found! Available actions:\n%s", "\n".join(list(dataset.keys()))
        )
    return dataset[action]


def _get_thermo_datasets():
    with open(
        "homeassistant/components/rasc/datasets/hvac-actions.csv", encoding="utf-8"
    ) as f:
        reader = csv.reader(f)

        src_dst_map = {}

        for row in reader:
            start, target, length = row
            if start == "temp_start":
                continue
            key = f"{math.floor(float(start))},{math.floor(float(target))}"

            if key not in src_dst_map:
                src_dst_map[key] = []

            src_dst_map[key].append(float(length))

        datasets = {}
        for key, values in src_dst_map.items():
            src_dst_map[key] = list(filter(lambda value: value < 3600, values))
            if len(values) > 50:
                datasets[key] = src_dst_map[key]
    return datasets
