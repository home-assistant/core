"""Test the TCP config flow."""

from collections.abc import Generator
import ssl
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.tcp.config_flow import build_unique_id
from homeassistant.components.tcp.const import CONF_OBJECT_ID, CONF_TITLE, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PAYLOAD,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT = {
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 4242,
    CONF_PAYLOAD: "status",
    "timeout": 10,
    "buffer_size": 1024,
    "ssl": False,
    "verify_ssl": True,
}

IMPORT_INPUT = {**USER_INPUT, CONF_TITLE: "TCP Sensor"}


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Avoid setting up the entry."""
    with patch(
        "homeassistant.components.tcp.async_setup_entry", return_value=None
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
    assert result["title"] == "127.0.0.1:4242"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == build_unique_id(USER_INPUT)


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
    assert result["result"].unique_id == build_unique_id(USER_INPUT)


async def test_user_flow_duplicate(hass: HomeAssistant) -> None:
    """Test a duplicate entry is aborted."""
    MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT, unique_id=build_unique_id(USER_INPUT)
    ).add_to_hass(hass)

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
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TCP Sensor"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == build_unique_id(USER_INPUT)


async def test_import_flow_duplicate(hass: HomeAssistant) -> None:
    """Test the import flow aborts on duplicates."""
    MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT, unique_id=build_unique_id(USER_INPUT)
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfiguring an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT, unique_id=build_unique_id(USER_INPUT)
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_input = {**USER_INPUT, CONF_PORT: 4343}
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == new_input
    assert entry.unique_id == build_unique_id(new_input)


async def test_reconfigure_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test the error shown when the server is unreachable."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT, unique_id=build_unique_id(USER_INPUT)
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    new_input = {**USER_INPUT, CONF_PORT: 4343}
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == USER_INPUT
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == new_input


async def test_user_flow_connection_error(hass: HomeAssistant) -> None:
    """Test a plain connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.tcp.config_flow.socket.create_connection",
        side_effect=OSError("Boom"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch("homeassistant.components.tcp.config_flow.socket.create_connection"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == build_unique_id(USER_INPUT)


async def test_user_flow_tls_handshake_fails(hass: HomeAssistant) -> None:
    """Test the TLS handshake is validated."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with (
        patch("homeassistant.components.tcp.config_flow.socket.create_connection"),
        patch(
            "homeassistant.components.tcp.config_flow.ssl.create_default_context"
        ) as mock_context,
    ):
        mock_context.return_value.wrap_socket.side_effect = ssl.SSLError("Boom")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**USER_INPUT, "ssl": True}
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


@pytest.mark.parametrize("verify_ssl", [True, False])
async def test_user_flow_tls_success(hass: HomeAssistant, verify_ssl: bool) -> None:
    """Test the handshake uses the configured verification setting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with (
        patch("homeassistant.components.tcp.config_flow.socket.create_connection"),
        patch(
            "homeassistant.components.tcp.config_flow.ssl.create_default_context"
        ) as mock_context,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**USER_INPUT, "ssl": True, "verify_ssl": verify_ssl}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert bool(mock_context.return_value.check_hostname) is verify_ssl
    assert result["result"].unique_id == build_unique_id(USER_INPUT)


async def test_same_endpoint_different_template(hass: HomeAssistant) -> None:
    """Test entries with different templates are not duplicates."""
    MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT, unique_id=build_unique_id(USER_INPUT)
    ).add_to_hass(hass)
    data = {**USER_INPUT, "value_template": "{{ value.split(';')[1] }}"}

    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={**data, CONF_TITLE: "B"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == data
    assert result["result"].unique_id == build_unique_id(data)


async def test_reconfigure_duplicate(hass: HomeAssistant) -> None:
    """Test reconfiguring into another entry's endpoint is aborted."""
    MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT, unique_id=build_unique_id(USER_INPUT)
    ).add_to_hass(hass)
    entry = MockConfigEntry(domain=DOMAIN, data={**USER_INPUT, CONF_PORT: 4343})
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_already_in_progress(hass: HomeAssistant) -> None:
    """Test concurrent flows for the same identity are aborted."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=False
    ):
        first = await hass.config_entries.flow.async_configure(
            first["flow_id"], USER_INPUT
        )
    assert first["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        second["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"

    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        first = await hass.config_entries.flow.async_configure(
            first["flow_id"], USER_INPUT
        )
    assert first["type"] is FlowResultType.CREATE_ENTRY
    assert first["result"].unique_id == build_unique_id(USER_INPUT)


async def test_reconfigure_keeps_import_data(hass: HomeAssistant) -> None:
    """Test the data stored by the import survives a reconfiguration."""
    data = {**USER_INPUT, CONF_PLATFORM: "binary_sensor", CONF_OBJECT_ID: "power"}
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id=build_unique_id(data))
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**USER_INPUT, CONF_PORT: 4343}
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {**data, CONF_PORT: 4343}


async def test_user_flow_duplicate_of_import(hass: HomeAssistant) -> None:
    """Test a UI entry cannot duplicate an imported one."""
    data = {**USER_INPUT, CONF_PLATFORM: "sensor", CONF_OBJECT_ID: "tcp_sensor"}
    MockConfigEntry(
        domain=DOMAIN, data=data, unique_id=build_unique_id(data)
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_sensor_and_binary_sensor_coexist(hass: HomeAssistant) -> None:
    """Test the same YAML config on two platforms is imported twice."""
    first = {**IMPORT_INPUT, CONF_PLATFORM: "sensor", CONF_OBJECT_ID: "tcp_sensor"}
    second = {**first, CONF_PLATFORM: "binary_sensor"}
    for data in (first, second):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=data
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == build_unique_id(
            {k: v for k, v in data.items() if k != CONF_TITLE}
        )


async def test_reconfigure_imported_with_sibling(hass: HomeAssistant) -> None:
    """Test an imported entry can be reconfigured next to its sibling."""
    sensor = {**USER_INPUT, CONF_PLATFORM: "sensor", CONF_OBJECT_ID: "tcp_sensor"}
    binary = {**sensor, CONF_PLATFORM: "binary_sensor", CONF_SCAN_INTERVAL: 60}
    MockConfigEntry(
        domain=DOMAIN, data=sensor, unique_id=build_unique_id(sensor)
    ).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN, data=binary, unique_id=build_unique_id(binary)
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.tcp.config_flow._can_connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SCAN_INTERVAL] == 60
