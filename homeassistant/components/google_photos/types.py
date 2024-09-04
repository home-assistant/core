"""Google Photos types."""

from google_photos_library_api.api import GooglePhotosLibraryApi

from homeassistant.config_entries import ConfigEntry

type GooglePhotosConfigEntry = ConfigEntry[GooglePhotosLibraryApi]
