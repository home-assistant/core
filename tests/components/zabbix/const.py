"""Constants for testing zabbix integration."""

from typing import Final

from homeassistant.components.zabbix.const import (
    CONF_PUBLISH_STATES_HOST,
    CONF_SENSOR_TRIGGERS,
    CONF_SENSOR_TRIGGERS_HOSTIDS,
    CONF_SENSOR_TRIGGERS_INDIVIDUAL,
    CONF_SENSOR_TRIGGERS_NAME,
    CONF_SENSORS,
    CONF_USE_API,
    CONF_USE_SENDER,
    CONF_USE_SENSORS,
    CONF_USE_TOKEN,
    DOMAIN,
    INCLUDE_EXCLUDE_FILTER,
)
from homeassistant.const import (
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PLATFORM,
    CONF_SSL,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.helpers.entityfilter import (
    CONF_ENTITY_GLOBS,
    CONF_EXCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITY_GLOBS,
)

MOCK_URL: Final = "https://zabbix_server.com:1111/"
MOCK_URL_NOPORT: Final = "https://zabbix_server.com/"
MOCK_BAD_TOKEN: Final = "123"
MOCK_GOOD_TOKEN: Final = (
    "11111111222222223333333344444444555555556666666677777777ffffffff"
)
MOCK_USERNAME: Final = "username"
MOCK_PASSWORD: Final = "password"

MOCK_PUBLISH_STATES_HOST: Final = "ha_publish_states_host"

MOCK_ZABBIX_API_VERSION: Final = 5.4

MOCK_CONFIG_DATA_SENSOR_TOKEN: Final = {
    CONF_URL: MOCK_URL,
    CONF_USE_API: True,
    CONF_USE_SENDER: False,
    CONF_USE_TOKEN: True,
    CONF_TOKEN: MOCK_GOOD_TOKEN,
    CONF_PUBLISH_STATES_HOST: MOCK_PUBLISH_STATES_HOST,
    INCLUDE_EXCLUDE_FILTER: {},
    CONF_USE_SENSORS: True,
    CONF_SENSORS: [
        {
            CONF_SENSOR_TRIGGERS: {
                CONF_SENSOR_TRIGGERS_NAME: None,
                CONF_SENSOR_TRIGGERS_HOSTIDS: [10051, 10081],
                CONF_SENSOR_TRIGGERS_INDIVIDUAL: True,
            }
        }
    ],
}

MOCK_CONFIG_DATA_SENSOR_USERPASS: Final = {
    CONF_URL: MOCK_URL,
    CONF_USE_API: True,
    CONF_USE_SENDER: False,
    CONF_USE_TOKEN: False,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_PUBLISH_STATES_HOST: MOCK_PUBLISH_STATES_HOST,
    INCLUDE_EXCLUDE_FILTER: {},
    CONF_USE_SENSORS: True,
    CONF_SENSORS: [
        {
            CONF_SENSOR_TRIGGERS: {
                CONF_SENSOR_TRIGGERS_NAME: None,
                CONF_SENSOR_TRIGGERS_HOSTIDS: [10051, 10081],
                CONF_SENSOR_TRIGGERS_INDIVIDUAL: True,
            }
        }
    ],
}

MOCK_FAKE_ENTITY: Final = "fake.entity"

MOCK_CONFIG_DATA_SENDER: Final = {
    CONF_URL: MOCK_URL_NOPORT,
    CONF_USE_API: True,
    CONF_USE_SENDER: True,
    CONF_USE_TOKEN: False,
    CONF_TOKEN: MOCK_GOOD_TOKEN,
    CONF_PUBLISH_STATES_HOST: MOCK_PUBLISH_STATES_HOST,
    INCLUDE_EXCLUDE_FILTER: {
        CONF_EXCLUDE_DOMAINS: ["device_tracker"],
        CONF_EXCLUDE_ENTITIES: ["sun.sun", "sensor.time"],
        CONF_INCLUDE_DOMAINS: ["alarm_control_panel", "light"],
        CONF_INCLUDE_ENTITIES: [MOCK_FAKE_ENTITY],
        CONF_INCLUDE_ENTITY_GLOBS: ["binary_sensor.*_occupancy"],
    },
    CONF_USE_SENSORS: False,
}

MOCK_CONFIGURATION_SENSOR_DATA_NO_TRIGGERS: Final = {
    "sensor": {CONF_PLATFORM: DOMAIN, CONF_SENSOR_TRIGGERS: None}
}

MOCK_CONFIGURATION_SENSOR_DATA_NO_NAME_NO_INDIVIDUAL_WITH_HOSTIDS: Final = {
    "sensor": {
        CONF_PLATFORM: DOMAIN,
        CONF_SENSOR_TRIGGERS: {
            CONF_SENSOR_TRIGGERS_NAME: "",
            CONF_SENSOR_TRIGGERS_HOSTIDS: [10051, 10081, 10084],
            CONF_SENSOR_TRIGGERS_INDIVIDUAL: False,
        },
    }
}

MOCK_ALL_HOSTS_TRIGGER_NAME: Final = "Important Hosts Trigger Count"
MOCK_CONFIGURATION_SENSOR_DATA_NO_INDIVIDUAL_NO_HOSTIDS: Final = {
    "sensor": {
        CONF_PLATFORM: DOMAIN,
        CONF_SENSOR_TRIGGERS: {
            CONF_SENSOR_TRIGGERS_NAME: MOCK_ALL_HOSTS_TRIGGER_NAME,
            CONF_SENSOR_TRIGGERS_INDIVIDUAL: False,
        },
    }
}

MOCK_CONFIGURATION_SENSOR_DATA_INDIVIDUAL_NO_HOSTIDS: Final = {
    "sensor": {
        CONF_PLATFORM: DOMAIN,
        CONF_SENSOR_TRIGGERS: {
            CONF_SENSOR_TRIGGERS_NAME: "",
            CONF_SENSOR_TRIGGERS_INDIVIDUAL: True,
        },
    }
}

MOCK_CONFIGURATION_SENSOR_DATA_INDIVIDUAL_WITH_HOSTIDS: Final = {
    "sensor": {
        CONF_PLATFORM: DOMAIN,
        CONF_SENSOR_TRIGGERS: {
            CONF_SENSOR_TRIGGERS_NAME: "",
            CONF_SENSOR_TRIGGERS_HOSTIDS: [10051, 10081, 10084, 10085, 10086],
            CONF_SENSOR_TRIGGERS_INDIVIDUAL: True,
        },
    }
}

MOCK_DATA: Final = {
    CONF_HOST: MOCK_URL,
    CONF_PATH: "ZABBIX_PATH",
    CONF_SSL: False,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_PUBLISH_STATES_HOST: MOCK_PUBLISH_STATES_HOST,
    CONF_EXCLUDE: {
        CONF_DOMAINS: ["device_tracker"],
        CONF_ENTITIES: ["sun.sun", "sensor.time"],
    },
    CONF_INCLUDE: {
        CONF_DOMAINS: ["alarm_control_panel", "light"],
        CONF_ENTITY_GLOBS: ["binary_sensor.*_occupancy"],
    },
}

MOCK_CONFIGURATION = {
    DOMAIN: {
        CONF_HOST: MOCK_URL,
        CONF_PATH: "ZABBIX_PATH",
        CONF_SSL: False,
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
        CONF_PUBLISH_STATES_HOST: MOCK_PUBLISH_STATES_HOST,
        CONF_EXCLUDE: {
            CONF_DOMAINS: ["device_tracker"],
            CONF_ENTITIES: ["sun.sun", "sensor.time"],
        },
        CONF_INCLUDE: {
            CONF_DOMAINS: ["alarm_control_panel", "light"],
            CONF_ENTITY_GLOBS: ["binary_sensor.*_occupancy"],
        },
    },
    "sensor": [
        {
            CONF_PLATFORM: DOMAIN,
            CONF_SENSOR_TRIGGERS: {
                CONF_SENSOR_TRIGGERS_NAME: "",
                CONF_SENSOR_TRIGGERS_HOSTIDS: [10051, 10081, 10084, 10085, 10086],
                CONF_SENSOR_TRIGGERS_INDIVIDUAL: True,
            },
        },
    ],
}
