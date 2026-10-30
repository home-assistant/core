"""Constants for the Anglian Water test suite."""

from homeassistant.components.anglian_water.helpers import consent_required_issue_id

ACCOUNT_NUMBER = "171266493"
ACCESS_TOKEN = "valid_token"
USERNAME = "hello@example.com"
PASSWORD = "SecurePassword123"

CONSENT_REQUIRED_ISSUE_ID = consent_required_issue_id(ACCOUNT_NUMBER)
