"""Constants for the route53 integration."""

from datetime import timedelta

DOMAIN = "route53"

CONF_ACCESS_KEY_ID = "aws_access_key_id"
CONF_SECRET_ACCESS_KEY = "aws_secret_access_key"
CONF_RECORDS = "records"

INTERVAL = timedelta(minutes=60)
DEFAULT_TTL = 300
