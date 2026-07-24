"""Constants for EC component."""

ATTR_OBSERVATION_TIME = "observation_time"
ATTR_STATION = "station"
CONF_STATION = "station"
CONF_TITLE = "title"
DOMAIN = "environment_canada"
SERVICE_ENVIRONMENT_CANADA_FORECASTS = "get_forecasts"

CONF_RADAR_LAYER = "radar_layer"
CONF_RADAR_LEGEND = "radar_legend"
CONF_RADAR_TIMESTAMP = "radar_timestamp"
CONF_RADAR_OPACITY = "radar_opacity"
CONF_RADAR_RADIUS = "radar_radius"
CONF_RADAR_DURATION = "radar_duration"
CONF_RADAR_FPS = "radar_fps"

RADAR_LAYERS = ["rain", "snow", "precip_type"]

# Defaults preserve the radar behaviour from before the options flow existed:
# the precipitation-type layer with the legend hidden.
DEFAULT_RADAR_LAYER = "precip_type"
DEFAULT_RADAR_LEGEND = False
DEFAULT_RADAR_TIMESTAMP = True
DEFAULT_RADAR_OPACITY = 65
DEFAULT_RADAR_RADIUS = 200
# 0 means use the full range of images Environment Canada reports as available.
DEFAULT_RADAR_DURATION = 0
DEFAULT_RADAR_FPS = 5
