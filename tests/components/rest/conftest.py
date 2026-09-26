"""Fixtures for REST component tests."""

from http import HTTPStatus
from typing import Any

import pytest

from homeassistant.components.rest import DOMAIN
from homeassistant.components.rest.const import (
    CONF_ENCODING,
    CONF_JSON_ATTRS,
    CONF_JSON_ATTRS_PATH,
    CONF_SSL_CIPHER_LIST,
    CONF_SSL_SECTION,
    DEFAULT_ENCODING,
    DEFAULT_METHOD,
    DEFAULT_SSL_CIPHER_LIST,
)
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_METHOD,
    CONF_RESOURCE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    Platform,
    UnitOfArea,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def async_mock_resource(aioclient_mock: AiohttpClientMocker) -> None:
    """Default mock resource."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, json={"key": "on"})


@pytest.fixture
def get_config_entry_data() -> dict[str, Any]:
    """Default config entry data."""
    return {
        CONF_RESOURCE: "http://localhost",
        CONF_METHOD: DEFAULT_METHOD,
        CONF_AUTHENTICATION: {CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION},
        CONF_SSL_SECTION: {
            CONF_VERIFY_SSL: True,
            CONF_SSL_CIPHER_LIST: DEFAULT_SSL_CIPHER_LIST,
        },
        CONF_ENCODING: DEFAULT_ENCODING,
    }


@pytest.fixture
def get_subentry_data() -> list[ConfigSubentryData]:
    """Default subentry data."""
    return [
        ConfigSubentryData(
            data={CONF_VALUE_TEMPLATE: '{{ value_json["key"] == "on"}}'},
            subentry_type=Platform.BINARY_SENSOR,
            title="binary sensor",
            unique_id=f"{Platform.BINARY_SENSOR}_1",
        ),
        ConfigSubentryData(
            data={
                CONF_FORCE_UPDATE: True,
                CONF_JSON_ATTRS: [{"item": "key"}, {"item": "location"}],
                CONF_JSON_ATTRS_PATH: "$.items[0]",
                CONF_DEVICE_CLASS: SensorDeviceClass.AREA,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                CONF_UNIT_OF_MEASUREMENT: UnitOfArea.SQUARE_METERS,
                CONF_VALUE_TEMPLATE: '{{ value_json["items"][0]["area"] }}',
            },
            subentry_type=Platform.SENSOR,
            title="sensor",
            unique_id=f"{Platform.SENSOR}_1",
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    data: dict[str, Any],
    subentries_data: list[ConfigSubentryData] | None = None,
) -> MockConfigEntry:
    """Set up a config entry for the REST component."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        subentries_data=subentries_data,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)

    return config_entry


@pytest.fixture
async def async_setup_complete_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[ConfigSubentryData],
) -> MockConfigEntry:
    """Get the default entry WITH default subentry data."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, json={"key": "on"})
    return await async_setup_entry(hass, get_config_entry_data, get_subentry_data)
