"""Tests for scrape component."""
from __future__ import annotations

from typing import Any


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
) -> dict[str, dict[str, Any]]:
    """Return config."""
    config = {
        "platform": "scrape",
        "resource": "https://www.home-assistant.io",
        "select": select,
        "name": name,
    }
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
        config["username"] = username
        config["password"] = password
    if headers:
        config["headers"] = headers
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
                "<div class='current-version material-card text'>"
                "<h1>Current Version: 2021.12.10</h1>Released: <span class='release-date'>January 17, 2022</span>"
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
