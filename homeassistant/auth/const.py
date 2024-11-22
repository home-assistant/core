"""Constants for the auth module."""

from datetime import timedelta

ACCESS_TOKEN_EXPIRATION = timedelta(minutes=30)
MFA_SESSION_EXPIRATION = timedelta(minutes=5)
REFRESH_TOKEN_EXPIRATION = timedelta(days=90).total_seconds()

GROUP_ID_ADMIN = "system-admin"
GROUP_ID_USER = "system-users"
GROUP_ID_READ_ONLY = "system-read-only"
