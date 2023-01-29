"""Class definitions for OneTracker API responses."""
from __future__ import annotations

from datetime import datetime

import logging

_LOGGER = logging.getLogger(__name__)


def parse_datetime(value: str) -> datetime | None:
    """Parse JSON datetime string to datetime or None."""
    if value == "1001-01-01T00:00:00Z":
        return None

    value = "2023-03-29T18:32:41.648465157Z"
    value = value[:-4]
    value += "Z"

    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")


class TrackingEvent:
    """A class definition for OneTracker tracking event data."""

    id: int
    parcel_id: int
    carrier_id: str
    carrier_name: str
    status: str
    text: str
    location: str
    latitude: float
    longitude: float
    time: datetime
    time_added: datetime

    def __init__(self, input_dict: dict | None = None) -> None:
        """Convert dictionary to class structure."""
        if input_dict is not None:
            for key, value in input_dict.items():
                if key.contains("time"):
                    setattr(self, key, parse_datetime(value))
                else:
                    setattr(self, key, value)

    def serialize(self) -> dict:
        """Serialize class data to dictionary."""
        return {
            "id": self.id,
            "parcel_id": self.parcel_id,
            "carrier_id": self.carrier_id,
            "carrier_name": self.carrier_name,
            "status": self.status,
            "text": self.text,
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "time": self.time,
            "time_added": self.time_added,
        }


class Parcel:
    """A class definition for OneTracker parcel data."""

    id: int
    user_id: int
    email_id: int
    email_sender: str
    retailer_name: str
    description: str
    notification_level: int
    is_archived: bool
    carrier: str
    carrier_name: str
    carrier_redirection_available: bool
    tracker_cached: bool
    tracking_id: str
    tracking_url: str | None = None
    tracking_status: str
    tracking_status_description: str
    tracking_status_text: str
    tracking_extra_info: str
    tracking_location: str
    tracking_time_estimated: datetime | None = None
    tracking_time_delivered: datetime | None = None
    tracking_lock: bool
    tracking_events: list[TrackingEvent] | None = None
    time_added: datetime
    time_updated: datetime

    def __init__(self, input_dict: dict | None = None) -> None:
        """Convert dictionary to class structure."""
        if input_dict is not None:
            for key, value in input_dict.items():
                if key.__contains__("time"):
                    setattr(self, key, parse_datetime(value))
                elif key == "tracking_events":
                    if value is not None:
                        setattr(self, key, map(TrackingEvent, value))
                    else:
                        setattr(self, key, list)
                else:
                    setattr(self, key, value)

    def serialize(self) -> dict:
        """Serialize class data to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_id": self.email_id,
            "email_sender": self.email_sender,
            "retailer_name": self.retailer_name,
            "description": self.description,
            "notification_level": self.notification_level,
            "is_archived": self.is_archived,
            "carrier": self.carrier,
            "carrier_name": self.carrier_name,
            "carrier_redirection_available": self.carrier_redirection_available,
            "tracker_cached": self.tracker_cached,
            "tracking_id": self.tracking_id,
            "tracking_url": self.tracking_url,
            "tracking_status": self.tracking_status,
            "tracking_status_description": self.tracking_status_description,
            "tracking_status_text": self.tracking_status_text,
            "tracking_extra_info": self.tracking_extra_info,
            "tracking_location": self.tracking_location,
            "tracking_time_estimated": self.tracking_time_estimated,
            "tracking_time_delivered": self.tracking_time_delivered,
            "tracking_lock": self.tracking_lock,
            "tracking_events": (
                lambda: map(lambda x: x.serialize(), self.tracking_events),
                lambda: None,
            )[self.tracking_events is not None](),
            "time_added": self.time_added,
            "time_updated": self.time_updated,
        }


class Session:
    """Class for storing OneTracker session."""

    user_id: int
    token: str
    expiration: datetime

    def __init__(self, input_dict: dict | None = None) -> None:
        """Convert dictionary to class structure."""
        if input_dict is not None:
            for key, value in input_dict.items():
                if key == "expiration":
                    setattr(self, key, parse_datetime(value))
                else:
                    setattr(self, key, value)


class APIResponse:
    """Base body for OneTracker api responses."""

    message: str


class TokenResponse(APIResponse):
    """Class for storing OneTracker response body."""

    session: Session

    def __init__(self, input_dict: dict | None = None) -> None:
        """Convert dictionary to class structure."""
        if input_dict is not None:
            for key, value in input_dict.items():
                if key == "session":
                    setattr(self, key, Session(value))
                else:
                    setattr(self, key, value)


class ParcelListResponse(APIResponse):
    """Class for storing OneTracker /parcels response body."""

    parcels: list[Parcel]

    def __init__(self, input_dict: dict | None = None) -> None:
        """Convert dictionary to class structure."""
        if input_dict is not None:
            for key, value in input_dict.items():
                if key == "parcels":
                    setattr(self, key, map(Parcel, value))
                else:
                    setattr(self, key, value)


class ParcelResponse(APIResponse):
    """Class for storing OneTracker /parcels/:parcel_id response body."""

    parcel: Parcel

    def __init__(self, input_dict: dict | None = None) -> None:
        """Convert dictionary to class structure."""
        if input_dict is not None:
            for key, value in input_dict.items():
                if key == "parcel":
                    setattr(self, key, Parcel(value))
                else:
                    setattr(self, key, value)
