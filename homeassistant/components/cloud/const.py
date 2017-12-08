"""Constants for the cloud component."""
DOMAIN = 'cloud'
CONFIG_DIR = '.cloud'
REQUEST_TIMEOUT = 10

SERVERS = {
    # Example entry:
    # 'production': {
    #     'cognito_client_id': '',
    #     'user_pool_id': '',
    #     'region': '',
    #     'relayer': ''
    # }
}

MESSAGE_EXPIRATION = """
It looks like your Home Assistant Cloud subscription has expired. Please check
your [account page](/config/cloud/account) to continue using the service.
"""
