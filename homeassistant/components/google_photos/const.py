"""Constants for the Google Photos integration."""

DOMAIN = "google_photos"

OAUTH2_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH2_TOKEN = "https://oauth2.googleapis.com/token"

UPLOAD_SCOPE = "https://www.googleapis.com/auth/photoslibrary.appendonly"
READ_SCOPE = "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
OAUTH2_SCOPES = [
    READ_SCOPE,
    UPLOAD_SCOPE,
    "https://www.googleapis.com/auth/userinfo.profile",
]
