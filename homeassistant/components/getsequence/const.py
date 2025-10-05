"""Constants for the Sequence integration."""

DOMAIN = "getsequence"

# Config flow
CONF_ACCESS_TOKEN = "access_token"
CONF_LIABILITY_ACCOUNTS = "liability_accounts"
CONF_INVESTMENT_ACCOUNTS = "investment_accounts"
CONF_LIABILITY_CONFIGURED = "liability_configured"

# API Configuration
API_BASE_URL = "https://api.getsequence.io"
API_TIMEOUT = 30

# Update intervals
SCAN_INTERVAL_SECONDS = 300  # 5 minutes

# Account types from Sequence API
ACCOUNT_TYPE_POD = "Pod"
ACCOUNT_TYPE_INCOME_SOURCE = "Income Source"
ACCOUNT_TYPE_LIABILITY = "Liability"
ACCOUNT_TYPE_INVESTMENT = "Investment"
ACCOUNT_TYPE_ACCOUNT = "Account"
ACCOUNT_TYPE_EXTERNAL = "External"

# Device info
MANUFACTURER = "Sequence Fintech Inc."
MODEL = "Financial Orchestration Platform"
