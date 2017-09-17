"""Constants for the cloud component."""
DOMAIN = 'cloud'
CONFIG_DIR = '.cloud'
REQUEST_TIMEOUT = 10
IOT_KEEP_ALIVE = 300

SUBSCRIBE_TOPIC_FORMAT = "{}/i/#"
PUBLISH_TOPIC_FORMAT = "{}/c/{}"
ALEXA_PUBLISH_TOPIC = "alexa/{}"

SERVERS = {
    # Example entry:
    # 'production': {
    #     'cognito_client_id': '',
    #     'user_pool_id': '',
    #     'region': '',
    #     'api_base': '',
    #     'iot_endpoint': ''
    # }
}
