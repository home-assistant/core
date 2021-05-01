"""Constants for the Flexpool integration."""

DOMAIN = "flexpool"

from homeassistant.const import CONF_NAME, CONF_ICON, CONF_TYPE

SENSOR_DICT = {
    "flexpool_unpaid_balance": {
        CONF_NAME: "Flexpool Unpaid Balance",
        CONF_ICON: "mdi:wallet",
    },
    "flexpool_current_reported": {
        CONF_NAME: "Flexpool Current Reported Hashrate",
        CONF_ICON: "mdi:pound",
        CONF_TYPE: "reported",
    },
    "flexpool_current_effective": {
        CONF_NAME: "Flexpool Current Effective Hashrate",
        CONF_ICON: "mdi:pound",
        CONF_TYPE: "effective",
    },
    "flexpool_daily_average": {
        CONF_NAME: "Flexpool Daily Average Hashrate",
        CONF_ICON: "mdi:pound",
        CONF_TYPE: "average",
    },
    "flexpool_worker_reported": {
        CONF_NAME: "Flexpool Worker Reported Hashrate",
        CONF_ICON: "mdi:pound",
        CONF_TYPE: "reported",
    },
    "flexpool_worker_effective": {
        CONF_NAME: "Flexpool Worker Effective Hashrate",
        CONF_ICON: "mdi:pound",
        CONF_TYPE: "effective",
    },
    "flexpool_worker_daily_valid": {
        CONF_NAME: "Flexpool Worker Daily Valid Shares",
        CONF_ICON: "mdi:share-variant",
        CONF_TYPE: "valid",
    },
    "flexpool_worker_daily_total": {
        CONF_NAME: "Flexpool Worker Daily Valid Shares",
        CONF_ICON: "mdi:share-variant",
        CONF_TYPE: "total",
    },
    "flexpool_effective": {
        CONF_NAME: "Flexpool Hashrate",
        CONF_ICON: "mdi:pound",
    },
    "flexpool_workers": {
        CONF_NAME: "Flexpool Workers",
        CONF_ICON: "mdi:pickaxe",
    },
    "flexpool_luck": {
        CONF_NAME: "Flexpool Current Luck",
        CONF_ICON: "mdi:clover",
    },
}
