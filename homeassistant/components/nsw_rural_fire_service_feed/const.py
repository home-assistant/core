"""Define constants for the NSW Rural Fire Service Feeds integration."""
from __future__ import annotations

from datetime import timedelta

CONF_CATEGORIES = "categories"

DEFAULT_RADIUS_IN_KM = 20.0
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

DOMAIN = "nsw_rural_fire_service_feed"

VALID_CATEGORIES = ["Advice", "Emergency Warning", "Not Applicable", "Watch and Act"]
