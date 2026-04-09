"""Constants for the SpaceAPI integration."""

CONF_CONTACT = "contact"
CONF_HUMIDITY = "humidity"
CONF_ICON_CLOSED = "icon_closed"
CONF_ICON_OPEN = "icon_open"
CONF_ICONS = "icons"
CONF_IRC = "irc"
CONF_SPACEFED = "spacefed"
CONF_SPACENET = "spacenet"
CONF_SPACESAML = "spacesaml"
CONF_CAM = "cam"
CONF_FEEDS = "feeds"
CONF_FEED_BLOG = "blog"
CONF_FEED_WIKI = "wiki"
CONF_FEED_CALENDAR = "calendar"
CONF_FEED_FLICKER = "flicker"
CONF_FEED_TYPE = "type"
CONF_FEED_URL = "url"
CONF_PROJECTS = "projects"
CONF_LOGO = "logo"
CONF_PHONE = "phone"
CONF_SIP = "sip"
CONF_KEYMASTERS = "keymasters"
CONF_KEYMASTER_NAME = "name"
CONF_KEYMASTER_IRC_NICK = "irc_nick"
CONF_KEYMASTER_PHONE = "phone"
CONF_KEYMASTER_EMAIL = "email"
CONF_KEYMASTER_TWITTER = "twitter"
CONF_TWITTER = "twitter"
CONF_FACEBOOK = "facebook"
CONF_ML = "ml"
CONF_MASTODON = "mastodon"
CONF_MATRIX = "matrix"
CONF_XMPP = "xmpp"
CONF_MUMBLE = "mumble"
CONF_GOPHER = "gopher"
CONF_SPACE = "space"
CONF_TEMPERATURE = "temperature"
CONF_BAROMETER = "barometer"
CONF_CARBONDIOXIDE = "carbondioxide"
CONF_POWER_CONSUMPTION = "power_consumption"
CONF_POWER_GENERATION = "power_generation"
CONF_ACCOUNT_BALANCE = "account_balance"
CONF_TOTAL_MEMBER_COUNT = "total_member_count"
CONF_PEOPLE_NOW_PRESENT = "people_now_present"
CONF_BEVERAGE_SUPPLY = "beverage_supply"
CONF_NETWORK_CONNECTIONS = "network_connections"
CONF_DOOR_LOCKED = "door_locked"

DATA_SPACEAPI = "data_spaceapi"
DOMAIN = "spaceapi"

SENSOR_TYPES = [
    CONF_TEMPERATURE,
    CONF_HUMIDITY,
    CONF_BAROMETER,
    CONF_CARBONDIOXIDE,
    CONF_POWER_CONSUMPTION,
    CONF_POWER_GENERATION,
    CONF_ACCOUNT_BALANCE,
    CONF_TOTAL_MEMBER_COUNT,
    CONF_PEOPLE_NOW_PRESENT,
    CONF_BEVERAGE_SUPPLY,
    CONF_NETWORK_CONNECTIONS,
    CONF_DOOR_LOCKED,
]
SPACEAPI_COMPATIBILITY = ["15"]

URL_API_SPACEAPI = "/api/spaceapi"
