"""Constants for the Alpha Bidet Infrared integration."""

from enum import StrEnum

DOMAIN = "alpha_bidet_infrared"
CONF_INFRARED_EMITTER_ENTITY_ID = "infrared_emitter_entity_id"


class AlphaBidetModel(StrEnum):
    """Alpha Bidet washlet models."""

    # The EW/EB/RW/RB suffixes are seat shape and color only.
    JX2 = "JX2"
