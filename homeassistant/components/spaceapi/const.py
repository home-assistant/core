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
CONF_FEED_FLICKR = "flickr"
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
CONF_RADIATION = "radiation"
CONF_NETWORK_TRAFFIC = "network_traffic"

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
    CONF_RADIATION,
    CONF_NETWORK_TRAFFIC,
]

SENSOR_DEFAULT_UNITS: dict[str, str] = {
    CONF_TEMPERATURE: "°C",
    CONF_HUMIDITY: "%",
    CONF_BAROMETER: "hPa",
    CONF_CARBONDIOXIDE: "ppm",
    CONF_POWER_CONSUMPTION: "W",
    CONF_POWER_GENERATION: "W",
    CONF_BEVERAGE_SUPPLY: "btl",
    CONF_ACCOUNT_BALANCE: "EUR",
    CONF_RADIATION: "µSv/h",
    CONF_NETWORK_TRAFFIC: "packets_per_second",
}
# Sensor types that require a unit per v15 spec
SENSOR_REQUIRES_UNIT = frozenset(SENSOR_DEFAULT_UNITS.keys())

CONF_MESSAGE = "message"
CONF_TRIGGER_PERSON = "trigger_person"
CONF_ACTIVITIES = "activities"
CONF_EVENTS_WINDOW_HOURS = "events_window_hours"

CONF_TIMEZONE = "timezone"
CONF_COUNTRY_CODE = "country_code"
CONF_HINT = "hint"

# Subentry type identifiers
SUBENTRY_LINK = "link"
SUBENTRY_MEMBERSHIP_PLAN = "membership_plan"
SUBENTRY_LINKED_SPACE = "linked_space"
SUBENTRY_LOCATION_AREA = "location_area"
SUBENTRY_WIND_SENSOR = "wind_sensor"

# Subentry field names
CONF_LINK_NAME = "name"
CONF_LINK_URL = "url"
CONF_LINK_DESCRIPTION = "description"

CONF_PLAN_NAME = "name"
CONF_PLAN_VALUE = "value"
CONF_PLAN_CURRENCY = "currency"
CONF_PLAN_BILLING_INTERVAL = "billing_interval"
CONF_PLAN_DESCRIPTION = "description"

CONF_LINKED_SPACE_ENDPOINT = "endpoint"
CONF_LINKED_SPACE_WEBSITE = "website"

CONF_AREA_NAME = "name"
CONF_AREA_DESCRIPTION = "description"
CONF_AREA_SQUARE_METERS = "square_meters"

CONF_WIND_SPEED = "speed"
CONF_WIND_GUST = "gust"
CONF_WIND_DIRECTION = "direction"
CONF_WIND_ELEVATION = "elevation"
CONF_WIND_NAME = "name"
CONF_WIND_LOCATION = "location"

BILLING_INTERVALS = [
    "yearly",
    "quarterly",
    "monthly",
    "weekly",
    "daily",
    "hourly",
    "other",
]

SPACEAPI_COMPATIBILITY = ["15"]

URL_API_SPACEAPI = "/api/spaceapi"

# SpaceAPI JSON response keys
ATTR_API_AREAS = "areas"
ATTR_API_CAM = "cam"
ATTR_API_CLOSED = "closed"
ATTR_API_CONTACT = "contact"
ATTR_API_EVENTS = "events"
ATTR_API_FEEDS = "feeds"
ATTR_API_LASTCHANGE = "lastchange"
ATTR_API_LAT = "lat"
ATTR_API_LINKED_SPACES = "linked_spaces"
ATTR_API_LINKS = "links"
ATTR_API_LON = "lon"
ATTR_API_LOGO = "logo"
ATTR_API_MEMBERSHIP_PLANS = "membership_plans"
ATTR_API_NAME = "name"
ATTR_API_OPEN = "open"
ATTR_API_PROJECTS = "projects"
ATTR_API_SENSOR_LOCATION = "location"
ATTR_API_SENSORS = "sensors"
ATTR_API_SPACE = "space"
ATTR_API_SPACEFED = "spacefed"
ATTR_API_TIMESTAMP = "timestamp"
ATTR_API_TYPE = "type"
ATTR_API_UNIT = "unit"
ATTR_API_URL = "url"
ATTR_API_VALUE = "value"
ATTR_API_WIND = "wind"
