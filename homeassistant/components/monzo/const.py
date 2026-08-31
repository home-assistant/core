"""Constants for the Monzo integration."""

from typing import Final

DOMAIN = "monzo"

ATTR_DATA: Final = "data"
CONF_CLOUDHOOK_URL: Final = "cloudhook_url"
CONF_WEBHOOK_URL: Final = "webhook_url"
EVENT_TRANSACTION_CREATED: Final = "transaction_created"
MONZO_WEBHOOK_TRANSACTION_CREATED: Final = "transaction.created"
