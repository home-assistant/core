"""Consts for using in modules."""

from homeassistant.const import Platform

DOMAIN = "bayesian"
PLATFORMS = [Platform.BINARY_SENSOR]
ATTR_OBSERVATIONS = "observations"
ATTR_OCCURRED_OBSERVATION_ENTITIES = "occurred_observation_entities"
ATTR_PROBABILITY = "probability"
ATTR_PROBABILITY_THRESHOLD = "probability_threshold"

CONF_OBSERVATIONS = "observations"
CONF_PRIOR = "prior"
CONF_TEMPLATE = "template"
CONF_NUMERIC_STATE = "numeric_state"
CONF_PROBABILITY_THRESHOLD = "probability_threshold"
CONF_P_GIVEN_F = "prob_given_false"
CONF_P_GIVEN_T = "prob_given_true"
CONF_TO_STATE = "to_state"
CONF_INDEX = "index"

DEFAULT_NAME = "Bayesian Binary Sensor"
DEFAULT_PROBABILITY_THRESHOLD = 0.5
