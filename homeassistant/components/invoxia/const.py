"""Constants for the Invoxia (unofficial) integration."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging

from gps_tracker.client.datatypes import TrackerIcon

ATTRIBUTION = "Data provided by an unofficial client for Invoxia API."

CLIENT = "client"

COORDINATORS = "coordinators"

DATA_UPDATE_INTERVAL = timedelta(minutes=4)

DOMAIN = "invoxia"

LOGGER = logging.getLogger(__package__)

MDI_ICONS: Mapping[TrackerIcon, str] = {
    TrackerIcon.OTHER: "mdi:cube",
    TrackerIcon.HANDBAG: "mdi:purse",
    TrackerIcon.BRIEFCASE: "mdi:briefcase",
    TrackerIcon.SUITCASE: "mdi:bag-suitcase",
    TrackerIcon.BACKPACK: "mdi:bag-personal",
    TrackerIcon.BIKE: "mdi:bicycle-basket",
    TrackerIcon.BOAT: "mdi:sail-boat",
    TrackerIcon.CAR: "mdi:car-hatchback",
    TrackerIcon.CARAVAN: "mdi:caravan",
    TrackerIcon.CART: "mdi:dolly",
    TrackerIcon.KAYAK: "mdi:kayaking",
    TrackerIcon.LAPTOP: "mdi:laptop",
    TrackerIcon.MOTO: "mdi:motorbike",
    TrackerIcon.HELICOPTER: "mdi:helicopter",
    TrackerIcon.PLANE: "mdi:airplane",
    TrackerIcon.SCOOTER: "mdi:moped",
    TrackerIcon.TENT: "mdi:tent",
    TrackerIcon.TRUCK: "mdi:truck",
    TrackerIcon.TRACTOR: "mdi:tractor",
    TrackerIcon.DOG: "mdi:dog",
    TrackerIcon.CAT: "mdi:cat",
    TrackerIcon.PERSON: "mdi:face-man",
    TrackerIcon.GIRL: "mdi:face-woman",
    TrackerIcon.BACKHOE_LOADER: "mdi:excavator",
    TrackerIcon.ANIMAL: "mdi:paw",
    TrackerIcon.WOMAN: "mdi:human-female",
    TrackerIcon.MAN: "mdi:human-male",
    TrackerIcon.EBIKE: "mdi:scooter",
    TrackerIcon.BEEHIVE: "mdi:beehive-outline",
    TrackerIcon.CARPARK: "mdi:garage",
    TrackerIcon.ANTENNA: "mdi:antenna",
    TrackerIcon.HEALTH: "mdi:hospital-box",
    TrackerIcon.KEYS: "mdi:key-chain-variant",
    TrackerIcon.WASHER: "mdi:washing-machine",
    TrackerIcon.TV: "mdi:television",
    TrackerIcon.PHONE: "mdi:cellphone",
}

TRACKERS = "trackers"
