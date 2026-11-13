"""Tests for the Bbox config flow."""

from unittest.mock import MagicMock

from bbox_api import (
    BboxConnectionError,
    BboxInvalidCredentialsError,
    BboxRateLimitError,
    DeviceInfo,
    FirmwareVersion,
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


async def test_user_flow_no_serial(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
) -> None:
    """Test a box answering without serial number cannot be configured."""
    mock_bbox_client.return_value.get_device.return_value = DeviceInfo(
        modelname="F@st5688b",
        numberofboots=1,
        serialnumber="",
        uptime=1,
        running=FirmwareVersion(version="25.1.22"),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    # Without a serial number there is no stable unique ID: show an error.
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    assert not hass.config_entries.async_entries(DOMAIN)

    # The flow must still finish once the box answers with its serial number.
    mock_bbox_client.return_value.get_device.return_value = DEVICE
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE.serialnumber


@pytest.mark.usefixtures("mock_bbox_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
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


@pytest.mark.usefixtures("mock_bbox_client")
async def test_user_flow_already_configured_imported_entry(
    hass: HomeAssistant,
) -> None:
    """Test the user flow aborts when an imported entry already covers the host."""
    imported = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        title=HOST,
        data={CONF_HOST: HOST, CONF_PASSWORD: "", CONF_VERIFY_SSL: True},
    )
    imported.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_bbox_client")
async def test_import_sensor_platform(hass: HomeAssistant) -> None:
    """Test the legacy sensor YAML platform is imported into a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            "platform": "bbox",
            CONF_HOST: DEFAULT_HOST,
            CONF_PASSWORD: "",
            CONF_VERIFY_SSL: True,
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


@pytest.mark.usefixtures("mock_bbox_client")
async def test_import_keeps_custom_host(hass: HomeAssistant) -> None:
    """Test a custom host in the YAML is kept verbatim as unique id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            "platform": "bbox",
            CONF_HOST: "192.168.1.254",
            CONF_PASSWORD: "",
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.254"
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "192.168.1.254"
    assert entry.data[CONF_HOST] == "192.168.1.254"


@pytest.mark.usefixtures("mock_bbox_client")
async def test_import_merges_platforms(hass: HomeAssistant) -> None:
    """Test the sensor and device_tracker YAML of one box merge into one entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            "platform": "bbox",
            CONF_HOST: HOST,
            CONF_PASSWORD: "",
            CONF_VERIFY_SSL: True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == HOST

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            "platform": "bbox",
            CONF_HOST: HOST,
            CONF_PASSWORD: "",
            CONF_VERIFY_SSL: True,
            CONF_MONITORED_VARIABLES: ALL_SENSORS,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST
    assert entry.data[CONF_MONITORED_VARIABLES] == ALL_SENSORS


@pytest.mark.usefixtures("mock_bbox_client")
async def test_import_merges_into_ui_entry(hass: HomeAssistant) -> None:
    """Test an import for a host set up through the UI merges into its entry."""
    ui_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE.serialnumber,
        title=HOST,
        data={CONF_HOST: HOST, CONF_PASSWORD: PASSWORD, CONF_VERIFY_SSL: False},
    )
    ui_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            "platform": "bbox",
            CONF_HOST: HOST,
            CONF_PASSWORD: "",
            CONF_VERIFY_SSL: True,
            CONF_MONITORED_VARIABLES: ALL_SENSORS,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    # The serial-number unique ID of the UI entry is kept.
    assert entry.unique_id == DEVICE.serialnumber
    assert entry.data[CONF_MONITORED_VARIABLES] == ALL_SENSORS
    # The saved connection settings are preserved: the platform schemas
    # insert password="" and verify_ssl=True when they are omitted.
    assert entry.data[CONF_PASSWORD] == PASSWORD
    assert entry.data[CONF_VERIFY_SSL] is False


@pytest.mark.usefixtures("mock_bbox_client")
async def test_import_merges_into_loaded_entry(hass: HomeAssistant) -> None:
    """Test a YAML re-import into a loaded entry keeps its settings and reloads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        title=HOST,
        data={
            CONF_HOST: HOST,
            CONF_PASSWORD: PASSWORD,
            CONF_VERIFY_SSL: False,
            CONF_MONITORED_VARIABLES: ["uptime"],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.bbox_number_of_reboot") is None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            "platform": "bbox",
            CONF_HOST: HOST,
            CONF_PASSWORD: "",
            CONF_VERIFY_SSL: True,
            CONF_MONITORED_VARIABLES: ALL_SENSORS,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    # The connection settings saved on the entry win over the schema defaults.
    assert entry.data[CONF_PASSWORD] == PASSWORD
    assert entry.data[CONF_VERIFY_SSL] is False
    assert entry.data[CONF_MONITORED_VARIABLES] == ALL_SENSORS
    # The merged entry reloads, so the newly monitored sensor appears.
    assert hass.states.get("sensor.bbox_number_of_reboot") is not None


@pytest.mark.parametrize(
    ("unique_id", "verify_ssl"),
    [
        pytest.param(DEVICE.serialnumber, False, id="serial-based entry"),
        pytest.param(HOST, True, id="host-based YAML entry"),
    ],
)
@pytest.mark.usefixtures("mock_bbox_client")
async def test_reconfigure_flow(
    hass: HomeAssistant, unique_id: str, verify_ssl: bool
) -> None:
    """Test reconfiguring to a new host adopts or keeps the serial unique ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        title=HOST,
        data={CONF_HOST: HOST, CONF_PASSWORD: PASSWORD, CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_PASSWORD: PASSWORD,
            CONF_VERIFY_SSL: verify_ssl,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # The unique ID is the serial number of the box: it does not change
    # when the box moves to a new IP address.
    assert entry.unique_id == DEVICE.serialnumber
    assert entry.data[CONF_HOST] == "192.168.1.1"
    assert entry.data[CONF_VERIFY_SSL] is verify_ssl
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_bbox_client")
async def test_reconfigure_flow_host_taken(hass: HomeAssistant) -> None:
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


async def test_reconfigure_flow_different_serial(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a serial-based entry cannot be repointed at another box."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_bbox_client.return_value.get_device.return_value = DeviceInfo(
        modelname="F@st5688b",
        numberofboots=1,
        serialnumber="OTHER123456789",
        uptime=1,
        running=FirmwareVersion(version="25.1.22"),
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.1", CONF_PASSWORD: PASSWORD, CONF_VERIFY_SSL: True},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_device"
    # The entry keeps its identity and its connection settings.
    assert mock_config_entry.unique_id == DEVICE.serialnumber
    assert mock_config_entry.data[CONF_HOST] == HOST


async def test_reconfigure_flow_no_serial(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a reconfigure against a box without serial number is rejected."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_bbox_client.return_value.get_device.return_value = DeviceInfo(
        modelname="F@st5688b",
        numberofboots=1,
        serialnumber="",
        uptime=1,
        running=FirmwareVersion(version="25.1.22"),
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD, CONF_VERIFY_SSL: True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # The reconfigure must still finish once the box answers with its serial.
    mock_bbox_client.return_value.get_device.return_value = DEVICE
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.1", CONF_PASSWORD: PASSWORD, CONF_VERIFY_SSL: True},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.unique_id == DEVICE.serialnumber
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.1"


@pytest.mark.usefixtures("mock_bbox_client")
async def test_reauth_flow(hass: HomeAssistant) -> None:
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
