"""Constants for the Appartme integration."""

ENVIRONMENT = "prod"
if ENVIRONMENT == "prod":
    ENV_SUFIX = ""
elif ENVIRONMENT == "preprod":
    ENV_SUFIX = "-preprod"
else:
    ENV_SUFIX = f"-{ENVIRONMENT}"

DOMAIN = "appartme"
OAUTH2_AUTHORIZE = f"https://web{ENV_SUFIX}.appartme.cloud/oAuth"
OAUTH2_TOKEN = (
    f"https://appartme-service{ENV_SUFIX}.appartme.cloud/paasapi/v1/oauth/token"
)
API_URL = f"https://api{ENV_SUFIX}.appartme.cloud/paasapi/v1"
UPDATE_INTERVAL_DEFAULT = 60
UPDATE_INTERVAL_MIN = 30
