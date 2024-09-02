"""Contains all the models used by the library."""

from typing import Any


class ContactInfo:
    """Class representing contact's information."""

    def __init__(self, json: dict[str, Any]) -> None:
        """Initialize ContactInfo."""
        self._contact_info_json = json

    @property
    def contact_id(self) -> str:
        """Return contact ID."""
        return str(self._contact_info_json.get("contactId"))

    @property
    def display_name(self) -> str:
        """Return name."""
        return str(self._contact_info_json.get("displayName"))

    @property
    def contact_type(self) -> str:
        """Return type."""
        return str(self._contact_info_json.get("contactType"))

    @property
    def picture_image_data(self) -> str | None:
        """Return image (Base64 encoded)."""
        return (
            str(self._contact_info_json.get("pictureImageData"))
            if self._contact_info_json.get("pictureImageData") is not None
            else None
        )

    @property
    def picture_url(self) -> str | None:
        """Return picture url."""
        return (
            str(self._contact_info_json.get("pictureUrl"))
            if self._contact_info_json.get("pictureUrl") is not None
            else None
        )


class Contact:
    """Class representing a Fing contact."""

    def __init__(self, json: dict[str, Any]) -> None:
        """Initialize Contact."""
        self._contact_json = json

    @property
    def state_change_time(self) -> str:
        """Return state change time."""
        return str(self._contact_json.get("stateChangeTime"))

    @property
    def contact_info(self) -> ContactInfo:
        """Return contact info."""
        return ContactInfo(json=self._contact_json["contactInfo"])

    @property
    def current_state(self) -> str | None:
        """Return current state."""
        return (
            str(self._contact_json.get("currentState"))
            if self._contact_json.get("currentState") is not None
            else None
        )

    @property
    def presence_device_details(self) -> str | None:
        """Return presence device details."""
        return (
            str(self._contact_json.get("presenceDeviceDetails"))
            if self._contact_json.get("presenceDeviceDetails") is not None
            else None
        )


class Device:
    """Class representing a device found by Fing."""

    def __init__(self, json: dict[str, Any]) -> None:
        """Initialize Device."""
        self._device_json = json

    @property
    def mac(self) -> str:
        """Return mac address."""
        return str(self._device_json["mac"])

    @property
    def ip(self) -> list[str]:
        """Return ip address."""
        return list[str](self._device_json["ip"])

    @property
    def active(self) -> bool:
        """Return state."""
        return self._device_json["state"] == "UP"

    @property
    def name(self) -> str | None:
        """Return name."""
        return (
            str(self._device_json.get("name"))
            if self._device_json.get("name") is not None
            else None
        )

    @property
    def type(self) -> str | None:
        """Return device type."""
        return (
            str(self._device_json.get("type"))
            if self._device_json.get("type") is not None
            else None
        )

    @property
    def make(self) -> str | None:
        """Return device maker."""
        return (
            str(self._device_json.get("make"))
            if self._device_json.get("make") is not None
            else None
        )

    @property
    def model(self) -> str | None:
        """Return device model."""
        return (
            str(self._device_json.get("model"))
            if self._device_json.get("model") is not None
            else None
        )

    @property
    def contactId(self) -> str | None:
        """Return contactId."""
        return (
            str(self._device_json.get("contactId"))
            if self._device_json.get("contactId") is not None
            else None
        )

    @property
    def first_seen(self) -> str | None:
        """Return first seen date-time."""
        return (
            str(self._device_json.get("first_seen"))
            if self._device_json.get("first_seen") is not None
            else None
        )

    @property
    def last_changed(self) -> str | None:
        """Return last changed date-time."""
        return (
            str(self._device_json.get("last_changed"))
            if self._device_json.get("last_changed") is not None
            else None
        )


class DeviceResponse:
    """Class representing the Device response data."""

    def __init__(self, json: dict[str, Any]) -> None:
        """Initialize the Device response object."""
        self._network_id = str(json.get("networkId"))
        self._devices = [Device(device_json) for device_json in json["devices"]]

    @property
    def network_id(self) -> str | None:
        """Return network ID."""
        return self._network_id

    @property
    def devices(self) -> list[Device]:
        """Return all the device found by Fing."""
        return self._devices


class ContactResponse:
    """Class representing the People response data."""

    def __init__(self, json: dict[str, Any]) -> None:
        """Initialize the People response object."""
        self._network_id = str(json["networkId"])
        self._last_change_time = str(json["lastChangeTime"])
        self._contacts = [Contact(contact_json) for contact_json in json["people"]]

    @property
    def network_id(self) -> str:
        """Return network ID."""
        return self._network_id

    @property
    def last_change_time(self) -> str:
        """Return the last change time."""
        return self._last_change_time

    @property
    def contacts(self) -> list[Contact]:
        """Return Fing's contacts."""
        return self._contacts
