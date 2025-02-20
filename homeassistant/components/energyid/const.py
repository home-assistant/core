"""Constants for the EnergyID integration.

Defines configuration keys, defaults, and valid metric kinds.
Used across the integration for consistent configuration handling.
"""

from typing import Final

DOMAIN: Final[str] = "energyid"

CONF_WEBHOOK_URL: Final["str"] = "webhook_url"
CONF_ENTITY_ID: Final["str"] = "entity_id"
CONF_METRIC: Final["str"] = "metric"
CONF_METRIC_KIND: Final["str"] = "metric_kind"
CONF_UNIT: Final["str"] = "unit"
DEFAULT_DATA_INTERVAL: Final["str"] = "P1D"
DEFAULT_UPLOAD_INTERVAL: Final[int] = 300

ENERGYID_METRIC_KINDS = ["cumulative", "total", "delta", "gauge"]
