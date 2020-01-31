"""Constants for the Hue component."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "hue"
API_NUPNP = "https://www.meethue.com/api/nupnp"

# How long to wait to actually do the refresh after requesting it.
# We wait some time so if we control multiple lights, we batch requests.
REQUEST_REFRESH_DELAY = 0.3
