"""Setup OneTrackerAPI for handling API connections."""

from datetime import datetime
import json

import logging
import httpx

from .api_responses import (
    Parcel,
    ParcelListResponse,
    ParcelResponse,
    Session,
    TokenResponse,
)

API_URL_BASE = "https://api.onetracker.app"
API_AUTH_HEADER_KEY = "x-api-token"

_LOGGER = logging.getLogger(__name__)


class OneTrackerAPI:
    """Wrapper for OneTracker API connections."""

    session: Session

    def __init__(self, email, password):
        """Initialize wrapper for OneTracker API connections."""
        _LOGGER.debug("Hit __init__")
        self.credentials = {"email": email, "password": password}

        self.refresh_token()

    def refresh_token(self) -> None:
        """Refresh token session using stored credentials."""
        _LOGGER.debug("Hit refresh_token")
        response = httpx.post(
            f"{API_URL_BASE}/auth/token", json=self.credentials
        ).json()
        response = TokenResponse(response)

        if response.message != "ok":
            raise OneTrackerAPIException("Invalid credentials!")

        self.session = response.session

    def __get_token(self) -> str:
        _LOGGER.warning("Token: %s", self.session.token)
        if self.session.expiration <= datetime.utcnow():
            self.refresh_token()

        return self.session.token

    def __get(self, path) -> dict:
        response = httpx.get(
            f"{API_URL_BASE}/{path}", headers={API_AUTH_HEADER_KEY: self.__get_token()}
        ).json()

        if response["message"] != "ok":
            raise OneTrackerAPIException(
                f"Error GET from '{path}': {json.dumps(response)}"
            )

        return response

    def get_parcels(self) -> dict[int, Parcel]:
        """Get all parcels from OneTracker."""
        dict_response = self.__get("parcels")

        response = ParcelListResponse(dict_response)

        return convert_parcels_to_dict(parcels=response.parcels)

    def get_parcel(self, parcel_id: int) -> Parcel:
        """Get data for specific parcel."""
        dict_response = self.__get(f"parcels/{parcel_id}")

        response = ParcelResponse(dict_response)

        return response.parcel

    def validate(self) -> bool:
        """Check for session being instantiated successfully."""
        return self.session is not None


def convert_parcels_to_dict(parcels: list[Parcel]) -> dict[int, Parcel]:
    """Convert lists with dict containing id to dict using ids as the key to reference each dict."""
    result = {}

    # _LOGGER.warning("Parcels: %s", json.dumps(parcels))
    for parcel in parcels:
        result[parcel.id] = parcel

    return result


class OneTrackerAPIException(Exception):
    """Custom exception class for OneTracker API exceptions."""
