"""Store constants used across the integration."""

from datetime import timedelta

ATTR_DOMAIN_NAME = "domain"
ATTR_RECORD_NAME = "record"
ATTR_RECORD_VALUE = "value"
ATTR_RECORD_TYPE = "type"

# Domain validation Regex
# from https://stackoverflow.com/questions/3026957/how-to-validate-a-domain-name-using-regex-php/16491074#16491074
DOMAIN_NAME_REGEX = r"^(?!\-)(?:(?:[a-zA-Z\d][a-zA-Z\d\-]{0,61})?[a-zA-Z\d]\.){1,126}(?!\d+)[a-zA-Z\d]{1,63}$"

MIN_TIME_BETWEEN_DOMAIN_UPDATES = timedelta(minutes=5)
