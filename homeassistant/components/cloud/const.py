"""Constants for the cloud component."""
DOMAIN = 'cloud'
CONFIG_DIR = '.cloud'
REQUEST_TIMEOUT = 10

SERVERS = {
    'production': {
        'cognito_client_id': '60i2uvhvbiref2mftj7rgcrt9u',
        'user_pool_id': 'us-east-1_87ll5WOP8',
        'region': 'us-east-1',
        'relayer': 'wss://cloud.hass.io:8000/websocket'
    }
}

MESSAGE_EXPIRATION = """
It looks like your Home Assistant Cloud subscription has expired. Please check
your [account page](/config/cloud/account) to continue using the service.
"""
