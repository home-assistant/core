"""Constants for the Whirlpool Appliances integration."""

from whirlpool.backendselector import Brand, Region

DOMAIN = "whirlpool"
CONF_BRAND = "brand"

REGIONS_CONF_MAP = {
    "EU": Region.EU,
    "US": Region.US,
}

BRANDS_CONF_MAP = {
    "Whirlpool": Brand.Whirlpool,
    "Maytag": Brand.Maytag,
    "KitchenAid": Brand.KitchenAid,
}
