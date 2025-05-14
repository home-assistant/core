"""Constants for the Google Photos integration."""

DOMAIN = "google_air_quality"

OAUTH2_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH2_TOKEN = "https://oauth2.googleapis.com/token"

UPLOAD_SCOPE = "https://www.googleapis.com/auth/photoslibrary.appendonly"
READ_SCOPE = "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
OAUTH2_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.profile",
]
