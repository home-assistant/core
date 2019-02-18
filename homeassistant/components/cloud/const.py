"""Constants for the cloud component."""
DOMAIN = 'cloud'
CONFIG_DIR = '.cloud'
REQUEST_TIMEOUT = 10

PREF_ENABLE_ALEXA = 'alexa_enabled'
PREF_ENABLE_GOOGLE = 'google_enabled'
PREF_GOOGLE_ALLOW_UNLOCK = 'google_allow_unlock'
PREF_CLOUDHOOKS = 'cloudhooks'

SERVERS = {
    'production': {
        'cognito_client_id': '60i2uvhvbiref2mftj7rgcrt9u',
        'user_pool_id': 'us-east-1_87ll5WOP8',
        'region': 'us-east-1',
        'relayer': 'wss://cloud.hass.io:8000/websocket',
        'google_actions_sync_url': ('https://24ab3v80xd.execute-api.us-east-1.'
                                    'amazonaws.com/prod/smart_home_sync'),
        'subscription_info_url': ('https://stripe-api.nabucasa.com/payments/'
                                  'subscription_info'),
        'cloudhook_create_url': 'https://webhooks-api.nabucasa.com/generate'
    }
}

MESSAGE_EXPIRATION = """
It looks like your Home Assistant Cloud subscription has expired. Please check
your [account page](/config/cloud/account) to continue using the service.
"""

MESSAGE_AUTH_FAIL = """
You have been logged out of Home Assistant Cloud because we have been unable
to verify your credentials. Please [log in](/config/cloud) again to continue
using the service.
"""
