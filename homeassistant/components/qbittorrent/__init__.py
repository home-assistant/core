"""The qbittorrent component."""
# import asyncio
# import logging

# from qbittorrent.client import Client, LoginRequired
# from requests.exceptions import RequestException
# import voluptuous as vol

# from homeassistant.components.sensor import PLATFORM_SCHEMA
# from homeassistant.const import (
#     CONF_MONITORED_VARIABLES,
#     CONF_NAME,
#     CONF_PASSWORD,
#     CONF_URL,
#     CONF_USERNAME,
#     DATA_RATE_KILOBYTES_PER_SECOND,
#     STATE_IDLE,
# )
# from homeassistant.exceptions import PlatformNotReady
# import homeassistant.helpers.config_validation as cv
# from homeassistant.helpers.entity import Entity

# from .const import (
#     SENSOR_TYPE_CURRENT_STATUS,
#     SENSOR_TYPE_DOWNLOAD_SPEED,
#     SENSOR_TYPE_UPLOAD_SPEED,
#     SENSOR_TYPE_TOTAL_TORRENTS,
#     SENSOR_TYPE_ACTIVE_TORRENTS,
#     SENSOR_TYPE_INACTIVE_TORRENTS,
#     SENSOR_TYPE_DOWNLOADING_TORRENTS,
#     SENSOR_TYPE_SEEDING_TORRENTS,
#     SENSOR_TYPE_RESUMED_TORRENTS,
#     SENSOR_TYPE_PAUSED_TORRENTS,
#     SENSOR_TYPE_COMPLETED_TORRENTS,
#     DEFAULT_NAME,
#     TRIM_SIZE,
#     CONF_CATEGORIES,
# )
