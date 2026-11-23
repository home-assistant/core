"""Tests for the Scrape diagnostics."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.scrape.const import (
    CONF_ADDITIONAL,
    CONF_AUTH,
    CONF_ENCODING,
    CONF_INDEX,
    CONF_SELECT,
    DEFAULT_ENCODING,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_RESOURCE,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("get_resource_config", "get_sensor_config"),
    [
        pytest.param(
            {
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "POST",
                CONF_PAYLOAD: "token=secret-payload",
                CONF_AUTH: {
                    CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
                    CONF_USERNAME: "secret-username",
                    CONF_PASSWORD: "secret-password",
                },
                CONF_ADDITIONAL: {
                    CONF_HEADERS: {"Authorization": "Bearer secret-token"},
                    CONF_VERIFY_SSL: False,
                    CONF_TIMEOUT: 10,
                    CONF_ENCODING: DEFAULT_ENCODING,
                },
            },
            (
                {
                    "data": {
                        CONF_ADDITIONAL: {
                            CONF_VALUE_TEMPLATE: "{{ value | trim }}",
                            CONF_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP,
                        },
                        CONF_INDEX: 0,
                        CONF_SELECT: ".utc-time",
                    },
                    "subentry_id": "01JZN07D8D23994A49YKS649S7",
                    "subentry_type": "entity",
                    "title": "Current time",
                    "unique_id": None,
                },
            ),
            id="credentials_and_headers",
        ),
        pytest.param(
            {
                CONF_RESOURCE: (
                    "https://user:secret-password@www.home-assistant.io/status"
                    "?api_key=secret-key"
                ),
                CONF_METHOD: "GET",
                CONF_AUTH: {},
                CONF_ADDITIONAL: {
                    CONF_VERIFY_SSL: True,
                    CONF_TIMEOUT: 10,
                    CONF_ENCODING: DEFAULT_ENCODING,
                },
            },
            (
                {
                    "data": {
                        CONF_ADDITIONAL: {},
                        CONF_INDEX: 0,
                        CONF_SELECT: ".current-version h1",
                    },
                    "subentry_id": "01JZN07D8D23994A49YKS649S7",
                    "subentry_type": "entity",
                    "title": "Current version",
                    "unique_id": None,
                },
            ),
            id="secrets_in_url",
        ),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    loaded_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics redact credentials, header values, payload and URL secrets."""
    assert loaded_entry.state is ConfigEntryState.LOADED
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, loaded_entry)
        == snapshot
    )
