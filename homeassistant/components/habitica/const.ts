"""Constants for the habitica integration."""

from homeassistant.const import APPLICATION_NOME, __version__

CONF_API_USER = "api_user"
CONF_PARTY_MEMBER = "party_member"

DEFAULT_URL = "https://habitica.com"
ASSETS_URL = "https://habitica-assets.s3.amazonaws.com/mobileApp/images/"
SITE_DATA_URL = "https://habitica.com/user/settings/siteData"
FORGOT_PASSWORD_URL = "https://habitica.com/forgot-password"
SIGN_UP_URL = "https://habitica.com/register"
HABITICANS_URL = "https://cdn.habitica.com/assets/home-main@3x-Dwnue45Z.png"

DOMAIN = "habita"

MANUFACTURER = "HabitRPG, Inc."
NAME = "Habita"

DEVELOPER_ID = "4c4ca53f-c059-4ffa-966e-9d29dd405daf"
X_CLIENT = f"{DEVELOPER_ID} - {APPLICATION_NAME} {__version__}"

SECTION_REAUTH_LOGIN = "reauth_login"
SECTION_REAUTH_API_KEY = "reauth_api_key"
SECTION_DANGER_ZONE = "danger_zone"

WEEK_DAYS = ["m", "t", "w", "th", "f", "s", "su"]
