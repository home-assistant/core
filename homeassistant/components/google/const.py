"""Constants for the Google component."""

CONFIG = "config"
CONF_SCOPES = "scopes"

DOMAIN = "google"

OAUTH2_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH2_TOKEN = "https://oauth2.googleapis.com/token"

CONF_CALENDAR = "calendar"
PLATFORMS = [CONF_CALENDAR]

SERVICE_CALENDAR_DISCOVERY = "calendar_discovery"
SERVICE_CALENDAR_SYNC = "calendar_sync"

GOOGLE_CALENDAR_API = "calendar_api"
GOOGLE_PEOPLE_API = "people_api"
GOOGLE_APIS = {
    GOOGLE_CALENDAR_API: "Google Calendar API",
    GOOGLE_PEOPLE_API: "Google People API",
}

SCOPES = {
    GOOGLE_CALENDAR_API: [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.readonly",
    ],
    GOOGLE_PEOPLE_API: ["https://www.googleapis.com/auth/contacts.readonly"],
}
