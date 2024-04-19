"""Constants for the Monzo integration."""

DOMAIN = "monzo"

OAUTH2_AUTHORIZE = "https://auth.monzo.com"
OAUTH2_TOKEN = "https://api.monzo.com/oauth2/token"

"""Services"""
SERVICE_POT_TRANSFER = "pot_transfer"

ATTR_AMOUNT = "amount"
DEFAULT_AMOUNT = 1

MONZO_EVENT = "monzo_event"
EVENT_TRANSACTION_CREATED = "transaction.created"

ACCOUNTS = "accounts"
POTS = "pots"

MODEL_POT = "Pot"
MODEL_CURRENT_ACCOUNT = "Current Account"
MODEL_JOINT_ACCOUNT = "Joint Account"

VALID_POT_TRANSFER_ACCOUNTS = {MODEL_CURRENT_ACCOUNT, MODEL_JOINT_ACCOUNT}

TRANSFER_ACCOUNTS = "source_account"
TRANSFER_TYPE = "transfer_type"
SOURCE_POTS = "source_pots"

DEPOSIT = "deposit"
WITHDRAW = "withdraw"
ACCOUNT_ID = "account_id"
ACCOUNT_TYPE = "type"

CONF_COORDINATOR = "coordinator"
