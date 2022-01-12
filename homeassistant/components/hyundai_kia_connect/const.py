"""Constants for the Hyundai / Kia Connect integration."""

DOMAIN: str = "hyundai_kia_connect"

CONF_BRAND: str = "brand"
CONF_FORCE_REFRESH_INTERVAL: str = "force_refresh"
CONF_NO_FORCE_REFRESH_HOUR_START: str = "no_force_refresh_hour_start"
CONF_NO_FORCE_REFRESH_HOUR_FINISH: str = "no_force_refresh_hour_finish"

REGION_EUROPE: str = "Europe"
REGION_CANADA: str = "Canada"
REGION_USA: str = "USA"
REGIONS = {1: REGION_EUROPE, 2: REGION_CANADA, 3: REGION_USA}
BRAND_KIA: str = "Kia"
BRAND_HYUNDAI: str = "Hyundai"
BRANDS = {1: BRAND_KIA, 2: BRAND_HYUNDAI}

DEFAULT_PIN: str = ""
DEFAULT_SCAN_INTERVAL: int = 30
DEFAULT_FORCE_REFRESH_INTERVAL: int = 240
DEFAULT_NO_FORCE_REFRESH_HOUR_START: int = 22
DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH: int = 6
