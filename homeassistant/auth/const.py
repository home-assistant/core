"""Constants for the auth module."""
from datetime import timedelta

ACCESS_TOKEN_EXPIRATION = timedelta(minutes=30)
MFA_SESSION_EXPIRATION = timedelta(minutes=5)
