"""Test the Scrape config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
import uuid

from homeassistant import config_entries
from homeassistant.components.rest.data import DEFAULT_TIMEOUT
from homeassistant.components.rest.schema import DEFAULT_METHOD
from homeassistant.components.scrape import DOMAIN
from homeassistant.components.scrape.const import (
    CONF_ENCODING,
    CONF_INDEX,
    CONF_SELECT,
    DEFAULT_ENCODING,
    DEFAULT_VERIFY_SSL,
)
from homeassistant.components.sensor import CONF_STATE_CLASS
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_METHOD,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_RESOURCE,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import MockRestData

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, get_data: MockRestData, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.rest.RestData",
        return_value=get_data,
    ) as mock_data:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "GET",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 10.0,
            },
        )
        await hass.async_block_till_done()
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["version"] == 1
    assert result3["options"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10.0,
        CONF_ENCODING: "UTF-8",
        "sensor": [
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            }
        ],
    }

    assert len(mock_data.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_post(
    hass: HomeAssistant, get_data: MockRestData, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form using POST method."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.rest.RestData",
        return_value=get_data,
    ) as mock_data:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "GET",
                CONF_PAYLOAD: "POST",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 10.0,
            },
        )
        await hass.async_block_till_done()
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["version"] == 1
    assert result3["options"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_PAYLOAD: "POST",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10.0,
        CONF_ENCODING: "UTF-8",
        "sensor": [
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            }
        ],
    }

    assert len(mock_data.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_fails(
    hass: HomeAssistant, get_data: MockRestData, mock_setup_entry: AsyncMock
) -> None:
    """Test config flow error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.rest.RestData",
        side_effect=HomeAssistantError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "GET",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 10.0,
            },
        )

    assert result2["errors"] == {"base": "resource_error"}

    with patch(
        "homeassistant.components.rest.RestData",
        return_value=MockRestData("test_scrape_sensor_no_data"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "GET",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 10.0,
            },
        )

    assert result2["errors"] == {"base": "resource_error"}

    with patch(
        "homeassistant.components.rest.RestData",
        return_value=get_data,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "GET",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 10.0,
            },
        )
        await hass.async_block_till_done()
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == "https://www.home-assistant.io"
    assert result4["options"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10.0,
        CONF_ENCODING: "UTF-8",
        "sensor": [
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            }
        ],
    }


async def test_options_resource_flow(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test options flow for a resource."""

    state = hass.states.get("sensor.current_version")
    assert state.state == "Current Version: 2021.12.10"

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "resource"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "resource"

    mocker = MockRestData("test_scrape_sensor2")
    with patch("homeassistant.components.rest.RestData", return_value=mocker):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: DEFAULT_METHOD,
                CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
                CONF_ENCODING: DEFAULT_ENCODING,
                CONF_USERNAME: "secret_username",
                CONF_PASSWORD: "secret_password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10.0,
        CONF_ENCODING: "UTF-8",
        CONF_USERNAME: "secret_username",
        CONF_PASSWORD: "secret_password",
        "sensor": [
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            }
        ],
    }

    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    # Check the state of the entity has changed as expected
    state = hass.states.get("sensor.current_version")
    assert state.state == "Hidden Version: 2021.12.10"


async def test_options_add_remove_sensor_flow(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test options flow to add and remove a sensor."""

    state = hass.states.get("sensor.current_version")
    assert state.state == "Current Version: 2021.12.10"

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_sensor"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_sensor"

    mocker = MockRestData("test_scrape_sensor2")
    with patch("homeassistant.components.rest.RestData", return_value=mocker), patch(
        "homeassistant.components.scrape.config_flow.uuid.uuid1",
        return_value=uuid.UUID("3699ef88-69e6-11ed-a1eb-0242ac120003"),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "Template",
                CONF_SELECT: "template",
                CONF_INDEX: 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10,
        CONF_ENCODING: "UTF-8",
        "sensor": [
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0,
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            },
            {
                CONF_NAME: "Template",
                CONF_SELECT: "template",
                CONF_INDEX: 0,
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120003",
            },
        ],
    }

    await hass.async_block_till_done()

    # Check the entity was updated, with the new entity
    assert len(hass.states.async_all()) == 2

    # Check the state of the entity has changed as expected
    state = hass.states.get("sensor.current_version")
    assert state.state == "Hidden Version: 2021.12.10"

    state = hass.states.get("sensor.template")
    assert state.state == "Trying to get"

    # Now remove the original sensor

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove_sensor"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "remove_sensor"

    mocker = MockRestData("test_scrape_sensor2")
    with patch("homeassistant.components.rest.RestData", return_value=mocker):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_INDEX: ["0"],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10,
        CONF_ENCODING: "UTF-8",
        "sensor": [
            {
                CONF_NAME: "Template",
                CONF_SELECT: "template",
                CONF_INDEX: 0,
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120003",
            },
        ],
    }

    await hass.async_block_till_done()

    # Check the original entity was removed, with only the new entity left
    assert len(hass.states.async_all()) == 1

    # Check the state of the new entity
    state = hass.states.get("sensor.template")
    assert state.state == "Trying to get"


async def test_options_edit_sensor_flow(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test options flow to edit a sensor."""

    state = hass.states.get("sensor.current_version")
    assert state.state == "Current Version: 2021.12.10"

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "select_edit_sensor"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "select_edit_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"index": "0"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "edit_sensor"

    mocker = MockRestData("test_scrape_sensor2")
    with patch("homeassistant.components.rest.RestData", return_value=mocker):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_SELECT: "template",
                CONF_INDEX: 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10,
        CONF_ENCODING: "UTF-8",
        "sensor": [
            {
                CONF_NAME: "Current version",
                CONF_SELECT: "template",
                CONF_INDEX: 0,
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            },
        ],
    }

    await hass.async_block_till_done()

    # Check the entity was updated
    assert len(hass.states.async_all()) == 1

    # Check the state of the entity has changed as expected
    state = hass.states.get("sensor.current_version")
    assert state.state == "Trying to get"


async def test_sensor_options_add_device_class(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test options flow to edit a sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_RESOURCE: "https://www.home-assistant.io",
            CONF_METHOD: DEFAULT_METHOD,
            CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_ENCODING: DEFAULT_ENCODING,
            "sensor": [
                {
                    CONF_NAME: "Current Temp",
                    CONF_SELECT: ".current-temp h3",
                    CONF_INDEX: 0,
                    CONF_VALUE_TEMPLATE: "{{ value.split(':')[1] }}",
                    CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
                }
            ],
        },
        entry_id="1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "select_edit_sensor"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "select_edit_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"index": "0"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "edit_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SELECT: ".current-temp h3",
            CONF_INDEX: 0.0,
            CONF_VALUE_TEMPLATE: "{{ value.split(':')[1] }}",
            CONF_DEVICE_CLASS: "temperature",
            CONF_STATE_CLASS: "measurement",
            CONF_UNIT_OF_MEASUREMENT: "°C",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10,
        CONF_ENCODING: "UTF-8",
        "sensor": [
            {
                CONF_NAME: "Current Temp",
                CONF_SELECT: ".current-temp h3",
                CONF_VALUE_TEMPLATE: "{{ value.split(':')[1] }}",
                CONF_INDEX: 0,
                CONF_DEVICE_CLASS: "temperature",
                CONF_STATE_CLASS: "measurement",
                CONF_UNIT_OF_MEASUREMENT: "°C",
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            },
        ],
    }


async def test_sensor_options_remove_device_class(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test options flow to edit a sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_RESOURCE: "https://www.home-assistant.io",
            CONF_METHOD: DEFAULT_METHOD,
            CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_ENCODING: DEFAULT_ENCODING,
            "sensor": [
                {
                    CONF_NAME: "Current Temp",
                    CONF_SELECT: ".current-temp h3",
                    CONF_INDEX: 0,
                    CONF_VALUE_TEMPLATE: "{{ value.split(':')[1] }}",
                    CONF_DEVICE_CLASS: "temperature",
                    CONF_STATE_CLASS: "measurement",
                    CONF_UNIT_OF_MEASUREMENT: "°C",
                    CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
                }
            ],
        },
        entry_id="1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "select_edit_sensor"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "select_edit_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"index": "0"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "edit_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SELECT: ".current-temp h3",
            CONF_INDEX: 0.0,
            CONF_VALUE_TEMPLATE: "{{ value.split(':')[1] }}",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10,
        CONF_ENCODING: "UTF-8",
        "sensor": [
            {
                CONF_NAME: "Current Temp",
                CONF_SELECT: ".current-temp h3",
                CONF_VALUE_TEMPLATE: "{{ value.split(':')[1] }}",
                CONF_INDEX: 0,
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            },
        ],
    }
