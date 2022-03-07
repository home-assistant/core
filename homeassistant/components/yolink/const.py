"""Constants for the yolink integration."""

DOMAIN = "yolink"
HOME_ID = "homeId"
HOME_SUBSCRIPTION = "home_subscription"

# TODO Update with your own urls
# OAUTH2_AUTHORIZE = "https://api.yosmart.com/oauth/v2/authorization.htm"
# OAUTH2_TOKEN = "https://api.yosmart.com/oauth/v2/getAccessToken.api"

YOLINK_HOST = "api.yosmart.com"
# YOLINK_HOST = "192.168.30.104"
YOLINK_HTTP_HOST = f"http://{YOLINK_HOST}:1080"
OAUTH2_AUTHORIZE = f"{YOLINK_HTTP_HOST}/oauth/v2/authorization.htm"
OAUTH2_TOKEN = f"{YOLINK_HTTP_HOST}/open/yolink/token"

YOLINK_API_GATE = f"{YOLINK_HTTP_HOST}/open/yolink/v2/api"
YOLINK_API_MQTT_BROKER = YOLINK_HOST
YOLINK_API_MQTT_BROKER_POER = 8003


class YoLinkError(Exception):
    """Base class for YoLink errors."""


class YoLinkAPIError(YoLinkError):
    """Errors during access YoLink API.

    code: Error Code
    desc: Desc or Error
    """

    def __init__(
        self,
        code: str,
        desc: str,
    ) -> None:
        """Initialize the yolink api error."""

        self.code = code
        self.message = desc
