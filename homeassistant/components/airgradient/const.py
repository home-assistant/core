"""Constants for the Airgradient integration."""

import logging

from airgradient import PmStandard

DOMAIN = "airgradient"

LOGGER = logging.getLogger(__package__)

PM_STANDARD = {
    PmStandard.UGM3: "ugm3",
    PmStandard.USAQI: "us_aqi",
}
PM_STANDARD_REVERSE = {v: k for k, v in PM_STANDARD.items()}
