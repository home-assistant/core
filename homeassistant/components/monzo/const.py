"""Constants for the Monzo integration."""

from typing import Final

DOMAIN = "monzo"

DEVICE_MODEL_ACCOUNT = "Account"
DEVICE_MODEL_POT = "Pot"

NON_TRANSFER_ACCOUNT_TYPES = frozenset({"uk_loan", "uk_monzo_flex", "uk_rewards"})
ATTR_DATA: Final = "data"
CONF_CLOUDHOOK_URL: Final = "cloudhook_url"
CONF_WEBHOOK_URL: Final = "webhook_url"
EVENT_TRANSACTION_CREATED: Final = "transaction_created"
MONZO_WEBHOOK_TRANSACTION_CREATED: Final = "transaction.created"
