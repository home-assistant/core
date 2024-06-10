"""Constants for zabbix integration."""

from typing import Final

DOMAIN = "zabbix"

# config_flow constants
ALL_ZABBIX_HOSTS: Final = "all_zabbix_hosts"
CONF_ADD_ANOTHER_SENSOR: Final = "add_another_sensor"
CONF_PUBLISH_STATES_HOST: Final = "publish_states_host"
CONF_PUBLISH_STATES_HOSTID: Final = "publish_states_hostid"
CONF_SENSOR_TRIGGERS: Final = "triggers"
CONF_SENSOR_TRIGGERS_HOSTIDS: Final = "hostids"
CONF_SENSOR_TRIGGERS_INDIVIDUAL: Final = "individual"
CONF_SENSOR_TRIGGERS_NAME: Final = "name"
CONF_SENSORS: Final = "sensors"
CONF_SKIP_CREATION_PUBLISH_STATES_HOST: Final = "skip_creation_publish_states_host"
CONF_USE_API: Final = "use_zabbix_api"
CONF_USE_SENDER: Final = "use_zabbix_sender"
CONF_USE_SENSORS: Final = "use_sensor"
CONF_USE_TOKEN: Final = "use_token"
INCLUDE_EXCLUDE_FILTER: Final = "include_exclude_filter"
DEFAULT_PUBLISH_STATES_HOST: Final = "homeassistant2"
DEFAULT_ZABBIX_HOSTGROUP_NAME: Final = "Home Assistant(s)"
DEFAULT_ZABBIX_TEMPLATE_NAME: Final = "Template Home Assistant"

# __init__ constants
BATCH_BUFFER_SIZE: Final = 100
BATCH_TIMEOUT: Final = 1
DEFAULT_PATH: Final = "zabbix"
DEFAULT_SSL: Final = False
DEFAULT_ZABBIX_SENDER_PORT: Final = 10051
ENTITIES_FILTER: Final = "entities_filter"
ENTRY_ID: Final = "entry_id"
NEW_CONFIG: Final = "new_config"
QUEUE_BACKLOG_SECONDS: Final = 30
RETRY_DELAY: Final = 20
RETRY_INTERVAL: Final = 60  # seconds
RETRY_MESSAGE: Final = f"%s Retrying in {RETRY_INTERVAL} seconds."
TIMEOUT: Final = 5
ZABBIX_SENDER: Final = "zabbix_sender"
ZABBIX_THREAD_INSTANCE: Final = "zabbix_thread_instance"
ZAPI: Final = "zabbix_api"

# sensor  constants
DEFAULT_TRIGGER_NAME: Final = "Zabbix"
