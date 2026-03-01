"""Constants for the AuroraWatch UK integration."""

from datetime import timedelta

DOMAIN = "aurorawatch"
ATTRIBUTION = "Data provided by AuroraWatch UK"

# API Configuration
API_URL = "http://aurorawatch-api.lancs.ac.uk/0.2/status/current-status.xml"
API_ACTIVITY_URL = (
    "https://aurorawatch-api.lancs.ac.uk/0.2/status/project/awn/sum-activity.xml"
)
API_TIMEOUT = 10  # seconds

# Update Configuration
UPDATE_INTERVAL = timedelta(minutes=5)

# Sensor Attributes
ATTR_LAST_UPDATED = "last_updated"
ATTR_PROJECT_ID = "project_id"
ATTR_SITE_ID = "site_id"
ATTR_SITE_URL = "site_url"
ATTR_API_VERSION = "api_version"
