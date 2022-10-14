"""Test the Amcrest config flow."""
from unittest.mock import patch

from amcrest import AmcrestError, LoginError

from homeassistant import config_entries
from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert len(result["errors"]) == 0

    data = {
        "host": "test-host",
        "name": "test name",
        "username": "test-user",
        "password": "test-password",
        "port": 80,
    }

    @property
    async def mock_async_serial_number(self):
        return "serial-number"

    with patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker.async_serial_number",
        new=mock_async_serial_number,
    ), patch(
        "homeassistant.components.amcrest.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], data
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test name"
    assert result2["data"] == data
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    @property
    async def mock_async_serial_number(self):
        raise LoginError()

    with patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker.async_serial_number",
        new=mock_async_serial_number,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "test-host",
                "name": "test name",
                "username": "test-user",
                "password": "test-password",
                "port": 80,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_bad_connection(hass: HomeAssistant) -> None:
    """Test we handle bad connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    @property
    async def mock_async_serial_number(self):
        raise AmcrestError()

    with patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker.async_serial_number",
        new=mock_async_serial_number,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "test-host",
                "name": "test name",
                "username": "test-user",
                "password": "test-password",
                "port": 80,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_other_exception(hass: HomeAssistant) -> None:
    """Test we handle other exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    @property
    async def mock_async_serial_number(self):
        raise ValueError()

    with patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker.async_serial_number",
        new=mock_async_serial_number,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "test-host",
                "name": "test name",
                "username": "test-user",
                "password": "test-password",
                "port": 80,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_flow_already_configured(hass: HomeAssistant) -> None:
    """Test we handle a flow that has already been configured."""
    first_entry = MockConfigEntry(domain=DOMAIN, unique_id="serial-number")
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert len(result["errors"]) == 0

    @property
    async def mock_async_serial_number(self):
        return "serial-number"

    with patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker.async_serial_number",
        new=mock_async_serial_number,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "test-host",
                "name": "test name",
                "username": "test-user",
                "password": "test-password",
                "port": 80,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_import(hass: HomeAssistant) -> None:
    """Test a YAML import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result["type"] == FlowResultType.FORM
    assert len(result["errors"]) == 0

    data = {
        "host": "test-host",
        "name": "test name",
        "username": "test-user",
        "password": "test-password",
        "port": 80,
    }

    @property
    async def mock_async_serial_number(self):
        return "serial-number"

    with patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker.async_serial_number",
        new=mock_async_serial_number,
    ), patch(
        "homeassistant.components.amcrest.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], data
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test name"
    assert result2["data"] == data
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options config flow."""
    mock_config_entry = MockConfigEntry(domain=DOMAIN, unique_id="serial-number")
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert "flow_id" in result

    data = {
        "ffmpeg_arguments": "-pred 1",
        "resolution": "high",
        "stream_source": "mjpeg",
        "binary_sensors": ["online", "motion_detected"],
        "sensors": ["sdcard"],
        "control_light": False,
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=data,
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == data


async def test_options_flow_exclusive_sensors(hass: HomeAssistant) -> None:
    """Test options config flow."""
    mock_config_entry = MockConfigEntry(domain=DOMAIN, unique_id="serial-number")
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert "flow_id" in result

    data = {
        "ffmpeg_arguments": "-pred 1",
        "resolution": "high",
        "stream_source": "mjpeg",
        "binary_sensors": ["online", "motion_detected", "motion_detected_polled"],
        "sensors": ["sdcard"],
        "control_light": False,
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=data,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "exclusive_binary_sensors"}
