"""Test APCUPSd config flow setup process."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.apcupsd.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import CONF_DATA, MOCK_MINIMAL_STATUS, MOCK_STATUS

from tests.common import MockConfigEntry


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test config flow setup with connection error."""
    with patch(
        "homeassistant.components.apcupsd.coordinator.aioapcaccess.request_status"
    ) as mock_get:
        mock_get.side_effect = OSError()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONF_DATA,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


async def test_config_flow_duplicate_host_port(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test duplicate config flow setup with the same host / port."""
    # First add an existing config entry to hass.
    mock_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="APCUPSd",
        data=CONF_DATA,
        unique_id=MOCK_STATUS["SERIALNO"],
        source=SOURCE_USER,
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.apcupsd.coordinator.aioapcaccess.request_status"
    ) as mock_request_status:
        # Assign the same host and port, which we should reject since the entry already exists.
        mock_request_status.return_value = MOCK_STATUS
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

        # Now we change the host with a different serial number and add it again. This should be successful.
        another_host = CONF_DATA | {CONF_HOST: "another_host"}
        mock_request_status.return_value = MOCK_STATUS | {
            "SERIALNO": MOCK_STATUS["SERIALNO"] + "ZZZ"
        }
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=another_host,
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == another_host


async def test_config_flow_duplicate_serial_number(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test duplicate config flow setup with different host but the same serial number."""
    # First add an existing config entry to hass.
    mock_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="APCUPSd",
        data=CONF_DATA,
        unique_id=MOCK_STATUS["SERIALNO"],
        source=SOURCE_USER,
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.apcupsd.coordinator.aioapcaccess.request_status"
    ) as mock_request_status:
        # Assign the different host and port, but we should still reject the creation since the
        # serial number is the same as the existing entry.
        mock_request_status.return_value = MOCK_STATUS
        another_host = CONF_DATA | {CONF_HOST: "another_host"}
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=another_host,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

        # Now we change the serial number and add it again. This should be successful.
        mock_request_status.return_value = MOCK_STATUS | {
            "SERIALNO": MOCK_STATUS["SERIALNO"] + "ZZZ"
        }
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=another_host
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == another_host


async def test_flow_works(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful creation of config entries via user configuration."""
    with patch(
        "homeassistant.components.apcupsd.coordinator.aioapcaccess.request_status",
        return_value=MOCK_STATUS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == MOCK_STATUS["UPSNAME"]
        assert result["data"] == CONF_DATA
        assert result["result"].unique_id == MOCK_STATUS["SERIALNO"]

        mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("extra_status", "expected_title"),
    [
        ({"UPSNAME": "Friendly Name"}, "Friendly Name"),
        ({"MODEL": "MODEL X"}, "MODEL X"),
        ({"SERIALNO": "ZZZZ"}, "ZZZZ"),
        # Some models report "Blank" as serial number, which we should treat it as not reported.
        ({"SERIALNO": "Blank"}, "APC UPS"),
        ({}, "APC UPS"),
    ],
)
async def test_flow_minimal_status(
    hass: HomeAssistant,
    extra_status: dict[str, str],
    expected_title: str,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test successful creation of config entries via user configuration when minimal status is reported.

    We test different combinations of minimal statuses, where the title of the
    integration will vary.
    """
    with patch(
        "homeassistant.components.apcupsd.coordinator.aioapcaccess.request_status"
    ) as mock_request_status:
        status = MOCK_MINIMAL_STATUS | extra_status
        mock_request_status.return_value = status

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=CONF_DATA
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == CONF_DATA
        assert result["title"] == expected_title
        mock_setup_entry.assert_called_once()


async def test_reconfigure_flow_works(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful reconfiguration of an existing entry."""
    mock_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="APCUPSd",
        data=CONF_DATA,
        unique_id=MOCK_STATUS["SERIALNO"],
        source=SOURCE_USER,
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # New configuration data with different host/port.
    new_conf_data = {CONF_HOST: "new_host", CONF_PORT: 4321}

    with patch(
        "homeassistant.components.apcupsd.coordinator.aioapcaccess.request_status",
        return_value=MOCK_STATUS,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_conf_data
        )
        await hass.async_block_till_done()
        mock_setup_entry.assert_called_once()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Check that the entry was updated with the new configuration.
    assert mock_entry.data[CONF_HOST] == new_conf_data[CONF_HOST]
    assert mock_entry.data[CONF_PORT] == new_conf_data[CONF_PORT]


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfiguration with connection error and recovery."""
    mock_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="APCUPSd",
        data=CONF_DATA,
        unique_id=MOCK_STATUS["SERIALNO"],
        source=SOURCE_USER,
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # New configuration data with different host/port.
    new_conf_data = {CONF_HOST: "new_host", CONF_PORT: 4321}
    with patch(
        "homeassistant.components.apcupsd.coordinator.aioapcaccess.request_status",
        side_effect=OSError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_conf_data
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    # Test recovery by fixing the connection issue.
    with patch(
        "homeassistant.components.apcupsd.coordinator.aioapcaccess.request_status",
        return_value=MOCK_STATUS,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_conf_data
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data == new_conf_data


@pytest.mark.parametrize(
    ("unique_id_before", "unique_id_after"),
    [
        (None, MOCK_STATUS["SERIALNO"]),
        (MOCK_STATUS["SERIALNO"], "Blank"),
        (MOCK_STATUS["SERIALNO"], MOCK_STATUS["SERIALNO"] + "ZZZ"),
    ],
)
async def test_reconfigure_flow_wrong_device(
    hass: HomeAssistant, unique_id_before: str | None, unique_id_after: str | None
) -> None:
    """Test reconfiguration with a different device (wrong serial number)."""
    mock_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="APCUPSd",
        data=CONF_DATA,
        unique_id=unique_id_before,
        source=SOURCE_USER,
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # New configuration data with different host/port.
    new_conf_data = {CONF_HOST: "new_host", CONF_PORT: 4321}
    # Make a copy of the status and modify the serial number if needed.
    mock_status = {k: v for k, v in MOCK_STATUS.items() if k != "SERIALNO"}
    mock_status["SERIALNO"] = unique_id_after
    with patch(
        "homeassistant.components.apcupsd.coordinator.aioapcaccess.request_status",
        return_value=mock_status,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_conf_data
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_apcupsd_daemon"
