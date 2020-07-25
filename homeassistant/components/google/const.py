"""Constants for the Google component."""

CONFIG = "config"
CONF_SCOPES = "scopes"

DOMAIN = "google"

# OAUTH2_AUTHORIZE = "https://accounts.google.com/o/oauth2/auth"
OAUTH2_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH2_TOKEN = "https://oauth2.googleapis.com/token"

CONF_CALENDAR = "calendar"
PLATFORMS = [CONF_CALENDAR]

SERVICE_CALENDAR_DISCOVERY = "calendar_discovery"
SERVICE_CALENDAR_SYNC = "calendar_sync"

# SCOPES are used by GoogleOAuth2FlowHandler
# SCOPES = [
#     "https://www.googleapis.com/auth/calendar",
#     # "https://www.googleapis.com/auth/contacts.readonly",
# ]

GOOGLE_CALENDAR_API = "calendar"
GOOGLE_PEOPLE_API = "people"
GOOGLE_APIS = {
    GOOGLE_CALENDAR_API: "Google Calendar API",
    GOOGLE_PEOPLE_API: "Google People API",
}

SCOPES = {
    GOOGLE_CALENDAR_API: ["https://www.googleapis.com/auth/calendar.readonly",],
    GOOGLE_PEOPLE_API: ["https://www.googleapis.com/auth/contacts.readonly",],
}

CLIENT_ID = "1007403502490-l693sinmq1llpdajoar1ibt3e9duo0kp.apps.googleusercontent.com"
CLIENT_SECRET = "UcjszAuvMSmD0k8o4IER8ieW"
