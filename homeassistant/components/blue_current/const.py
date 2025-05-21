"""Constants for the Blue Current integration."""

import logging

DOMAIN = "blue_current"

LOGGER = logging.getLogger(__package__)

EVSE_ID = "evse_id"
MODEL_TYPE = "model_type"
CARD = "card"
UID = "uid"
BCU_APP = "BCU-APP"
DEFAULT_CARD = {"id": BCU_APP, "uid": BCU_APP}
