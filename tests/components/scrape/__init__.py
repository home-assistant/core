"""Tests for scrape component."""
from __future__ import annotations

from typing import Any


def return_integration_config(
    *,
    authentication=None,
    username=None,
    password=None,
    headers=None,
    sensors=None,
) -> dict[str, dict[str, Any]]:
    """Return config."""
    config = {
        "resource": "https://www.home-assistant.io",
        "verify_ssl": True,
        "sensor": sensors,
    }
    if authentication:
        config["authentication"] = authentication
    if username:
        config["username"] = username
        config["password"] = password
    if headers:
        config["headers"] = headers

    return config


def return_config(
    select,
    name,
    *,
    attribute=None,
    index=None,
    template=None,
    uom=None,
    device_class=None,
    state_class=None,
    authentication=None,
    username=None,
    password=None,
    headers=None,
    unique_id=None,
    remove_platform=False,
) -> dict[str, dict[str, Any]]:
    """Return config."""
    config = {
        "platform": "scrape",
        "resource": "https://www.home-assistant.io",
        "select": select,
        "name": name,
        "index": 0,
        "verify_ssl": True,
    }
    if remove_platform:
        config.pop("platform")
    if attribute:
        config["attribute"] = attribute
    if index:
        config["index"] = index
    if template:
        config["value_template"] = template
    if uom:
        config["unit_of_measurement"] = uom
    if device_class:
        config["device_class"] = device_class
    if state_class:
        config["state_class"] = state_class
    if authentication:
        config["authentication"] = authentication
    if username:
        config["username"] = username
        config["password"] = password
    if headers:
        config["headers"] = headers
    if unique_id:
        config["unique_id"] = unique_id
    return config


class MockRestData:
    """Mock RestData."""

    def __init__(
        self,
        payload,
    ):
        """Init RestDataMock."""
        self.data: str | None = None
        self.payload = payload
        self.count = 0

    async def async_update(self, data: bool | None = True) -> None:
        """Update."""
        self.count += 1
        if self.payload == "test_scrape_sensor":
            self.data = (
                # Default
                "<div class='current-version material-card text'>"
                "<h1>Current Version: 2021.12.10</h1>Released: <span class='release-date'>January 17, 2022</span>"
                "<div class='links' style='links'><a href='/latest-release-notes/'>Release notes</a></div></div>"
                "<template>Trying to get</template>"
                "<div class='current-time'>"
                "<h1>Current Time:</h1><span class='utc-time'>2022-12-22T13:15:30Z</span>"
                "</div>"
            )
        if self.payload == "test_scrape_sensor2":
            self.data = (
                # Hidden version
                "<div class='current-version material-card text'>"
                "<h1>Hidden Version: 2021.12.10</h1>Released: <span class='release-date'>January 17, 2022</span>"
                "<div class='links' style='links'><a href='/latest-release-notes/'>Release notes</a></div></div>"
                "<template>Trying to get</template>"
            )
        if self.payload == "test_scrape_uom_and_classes":
            self.data = (
                "<div class='current-temp temp-card text'>"
                "<h3>Current Temperature: 22.1</h3>"
                "<div class='links'><a href='/check_temp/'>Temp check</a></div></div>"
            )
        if self.payload == "test_scrape_sensor_authentication":
            self.data = "<div class='return'>secret text</div>"
        if self.payload == "test_scrape_sensor_no_data":
            self.data = None
        if self.count == 3:
            self.data = None
