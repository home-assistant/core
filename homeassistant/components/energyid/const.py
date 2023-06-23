"""Constants for the EnergyID integration."""

from typing import Final

DOMAIN: Final[str] = "energyid"

CONF_WEBHOOK_URL: Final["str"] = "webhook_url"
CONF_ENTITY_ID: Final["str"] = "entity_id"
CONF_METRIC: Final["str"] = "metric"
CONF_METRIC_KIND: Final["str"] = "metric_kind"
CONF_UNIT: Final["str"] = "unit"
CONF_DATA_INTERVAL: Final["str"] = "data_interval"
DEFAULT_DATA_INTERVAL: Final["str"] = "P1D"
CONF_UPLOAD_INTERVAL: Final["str"] = "upload_interval"
DEFAULT_UPLOAD_INTERVAL: Final[int] = 300

ENERGYID_INTERVALS = ["P1M", "P1D", "PT1H", "PT15M", "PT5M"]
ENERGYID_METRIC_KINDS = ["cumulative", "total", "delta", "gauge"]
