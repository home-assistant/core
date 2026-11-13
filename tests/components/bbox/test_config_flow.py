"""Tests for the Bbox config flow."""

from unittest.mock import MagicMock

from bbox_api import (
    BboxConnectionError,
    BboxInvalidCredentialsError,
    BboxRateLimitError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.bbox.const import DEFAULT_HOST, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import ALL_SENSORS, DEVICE, HOST, PASSWORD

USER_INPUT = {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD, CONF_VERIFY_SSL: True}


async def test_user_flow(hass: HomeAssistant, mock_bbox_client: MagicMock) -> None:
    """Test the happy path of the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == USER_INPUT
    # The unique ID is the serial number of the box, stable across IP changes.
    assert result["result"].unique_id == DEVICE.serialnumber
    # The validation must hit an endpoint that requires authentication
    # (/device answers 200 without a login on current firmwares); the error
    # tests below pin this by raising on get_hosts and expecting form errors.
    mock_bbox_client.return_value.get_hosts.assert_awaited()


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (BboxConnectionError("unreachable"), "cannot_connect"),
        (BboxInvalidCredentialsError(), "invalid_auth"),
        (BboxRateLimitError(), "rate_limited"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, mock_bbox_client: MagicMock, error: Exception, reason: str
) -> None:
    """Test the user flow reports connection and auth errors on the form."""
    mock_bbox_client.return_value.get_hosts.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    # The flow must still finish once the cause is fixed.
    mock_bbox_client.return_value.get_hosts.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE.serialnumber


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a second flow for the same host aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_sensor_platform(
    hass: HomeAssistant, mock_bbox_client: MagicMock
) -> None:
    """Test the legacy sensor YAML platform is imported into a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            "platform": "bbox",
            CONF_MONITORED_VARIABLES: ALL_SENSORS,
            CONF_NAME: "Bbox",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_HOST
    # Imported entries have no password, so the unique ID stays host-based.
    assert result["result"].unique_id == DEFAULT_HOST
    assert result["data"] == {
        CONF_HOST: DEFAULT_HOST,
        CONF_PASSWORD: "",
        CONF_VERIFY_SSL: True,
        CONF_NAME: "Bbox",
        CONF_MONITORED_VARIABLES: ALL_SENSORS,
    }


async def test_import_keeps_custom_host(
    hass: HomeAssistant, mock_bbox_client: MagicMock
) -> None:
    """Test a custom host in the YAML is kept verbatim as unique id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={"platform": "bbox", CONF_HOST: "192.168.1.254"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.254"
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "192.168.1.254"
    assert entry.data[CONF_HOST] == "192.168.1.254"


async def test_import_merges_platforms(
    hass: HomeAssistant, mock_bbox_client: MagicMock
) -> None:
    """Test the sensor and device_tracker YAML of one box merge into one entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={"platform": "bbox", CONF_HOST: HOST},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == HOST

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={"platform": "bbox", CONF_MONITORED_VARIABLES: ALL_SENSORS},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST
    assert entry.data[CONF_MONITORED_VARIABLES] == ALL_SENSORS


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring the entry to a new host (box moved to 192.168.1.1)."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.1", CONF_PASSWORD: PASSWORD, CONF_VERIFY_SSL: False},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # The unique ID is the serial number of the box: it does not change
    # when the box moves to a new IP address.
    assert mock_config_entry.unique_id == DEVICE.serialnumber
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.1"
    assert mock_config_entry.data[CONF_VERIFY_SSL] is False
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_reconfigure_flow_host_taken(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
) -> None:
    """Test reconfigure aborts when the new host is another configured box."""
    other = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE.serialnumber,
        title="192.168.1.1",
        data={CONF_HOST: "192.168.1.1", CONF_PASSWORD: PASSWORD, CONF_VERIFY_SSL: True},
    )
    other.add_to_hass(hass)
    # The reconfigured entry still has a legacy host-based unique ID (YAML import).
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        title=HOST,
        data={CONF_HOST: HOST, CONF_PASSWORD: PASSWORD, CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.1", CONF_PASSWORD: PASSWORD, CONF_VERIFY_SSL: True},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(hass: HomeAssistant, mock_bbox_client: MagicMock) -> None:
    """Test an imported entry without password is reauthenticated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        title=HOST,
        data={CONF_HOST: HOST, CONF_PASSWORD: "", CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: PASSWORD, CONF_VERIFY_SSL: True}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == PASSWORD
    assert entry.state is ConfigEntryState.LOADED
