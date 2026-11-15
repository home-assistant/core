"""Test the TCP config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.tcp.const import CONF_TITLE, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PAYLOAD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT = {
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 4242,
    CONF_PAYLOAD: "status",
    CONF_TITLE: "TCP Sensor",
    "timeout": 10,
    "buffer_size": 1024,
    "ssl": False,
    "verify_ssl": True,
}


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Avoid setting up the entry."""
    with patch(
        "homeassistant.components.tcp.async_setup_entry", return_value=True
    ) as mock:
        yield mock


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TCP Sensor"
    assert result["data"] == USER_INPUT


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test the error is shown and the flow recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate(hass: HomeAssistant) -> None:
    """Test a duplicate entry is aborted."""
    MockConfigEntry(domain=DOMAIN, data=USER_INPUT).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test the import flow creates an entry."""
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


async def test_import_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test the import flow aborts when the server is unreachable."""
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=False
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_flow_duplicate(hass: HomeAssistant) -> None:
    """Test the import flow aborts on duplicates."""
    MockConfigEntry(domain=DOMAIN, data=USER_INPUT).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfiguring an entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, title="TCP Sensor")
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_input = {**USER_INPUT, CONF_PORT: 4343, CONF_TITLE: "Nuovo"}
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == new_input
    assert entry.title == "Nuovo"


async def test_reconfigure_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test the error shown when the server is unreachable."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
