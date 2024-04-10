"""Constants for the Whirlpool Appliances integration."""

from whirlpool.backendselector import Brand, Region

DOMAIN = "whirlpool"
CONF_BRAND = "brand"

CONF_REGIONS_MAP = {
    "EU": Region.EU,
    "US": Region.US,
}

CONF_BRANDS_MAP = {
    "Whirlpool": Brand.Whirlpool,
    "Maytag": Brand.Maytag,
    "KitchenAid": Brand.KitchenAid,
}
