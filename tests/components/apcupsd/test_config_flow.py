"""Test APCUPSd config flow setup process."""
from copy import copy
from unittest.mock import patch

from homeassistant.components.apcupsd import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_RESOURCES, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import CONF_DATA, MOCK_MINIMAL_STATUS, MOCK_STATUS

from tests.common import MockConfigEntry


def _patch_setup():
    return patch(
        "homeassistant.components.apcupsd.async_setup_entry",
        return_value=True,
    )


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test config flow setup with connection error."""
    with patch("apcaccess.status.get") as mock_get:
        mock_get.side_effect = OSError()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONF_DATA,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


async def test_config_flow_no_status(hass: HomeAssistant) -> None:
    """Test config flow setup with successful connection but no status is reported."""
    with patch(
        "apcaccess.status.parse",
        return_value={},  # Returns no status.
    ), patch("apcaccess.status.get", return_value=b""):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_status"


async def test_config_flow_duplicate(hass: HomeAssistant) -> None:
    """Test duplicate config flow setup."""

    # First add an exiting config entry to hass.
    mock_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="APCUPSd",
        data=CONF_DATA,
        unique_id=MOCK_STATUS["SERIALNO"],
        source=SOURCE_USER,
    )
    mock_entry.add_to_hass(hass)

    with patch("apcaccess.status.parse") as mock_parse, patch(
        "apcaccess.status.get", return_value=b""
    ), _patch_setup():
        mock_parse.return_value = MOCK_STATUS

        # Now, create the integration again using the same config data, we should reject
        # the creation due same host / port.
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONF_DATA,
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"

        # Then, we create the integration once again, using a different port. However,
        # this keep the apcaccess patch to report the same serial number, we should
        # reject the creation as well.
        another_host = {
            CONF_HOST: CONF_DATA[CONF_HOST],
            CONF_PORT: CONF_DATA[CONF_PORT] + 1,
        }
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=another_host,
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"

        # Now we change the serial number and add it again.
        another_device_status = copy(MOCK_STATUS)
        another_device_status["SERIALNO"] = MOCK_STATUS["SERIALNO"] + "ZZZ"
        mock_parse.return_value = another_device_status

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=another_host,
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == another_host
        assert result["title"] == "APCUPSd"


async def test_flow_works(hass: HomeAssistant) -> None:
    """Test successful creation of config entries via user configuration."""
    with patch("apcaccess.status.parse", return_value=MOCK_STATUS), patch(
        "apcaccess.status.get", return_value=b""
    ), _patch_setup() as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == SOURCE_USER

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_DATA
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "APCUPSd"
        assert result["data"] == CONF_DATA

        mock_setup.assert_called_once()


async def test_flow_works_minimal_status(hass: HomeAssistant) -> None:
    """Test successful creation of config entries via user configuration when APCUPSd reports limited number of statuses."""
    with patch("apcaccess.status.parse", return_value=MOCK_MINIMAL_STATUS), patch(
        "apcaccess.status.get", return_value=b""
    ), _patch_setup() as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == SOURCE_USER

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_DATA
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "APCUPSd"
        assert result["data"] == CONF_DATA

        mock_setup.assert_called_once()


async def test_flow_import(hass: HomeAssistant) -> None:
    """Test successful creation of config entries via YAML import."""
    with patch("apcaccess.status.parse", return_value=MOCK_STATUS), patch(
        "apcaccess.status.get", return_value=b""
    ), _patch_setup() as mock_setup:
        # Importing from YAML will create an extra field CONF_RESOURCES in the config
        # entry, here we test if it is properly stored.
        resources = ["MODEL"]

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=CONF_DATA | {CONF_RESOURCES: resources},
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "APCUPSd"
        assert result["data"] == CONF_DATA | {CONF_RESOURCES: resources}

        mock_setup.assert_called_once()


async def test_flow_import_with_invalid_resource(hass: HomeAssistant) -> None:
    """Test successful creation of config entries via YAML with invalid resources."""
    with patch("apcaccess.status.parse", return_value=MOCK_STATUS), patch(
        "apcaccess.status.get", return_value=b""
    ), _patch_setup() as mock_setup:
        # Give an unavailable but valid resource "REG1" to options, HA should simply
        # ignore this resource during import and not crash.
        resources = ["MODEL", "REG1"]
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=CONF_DATA | {CONF_RESOURCES: resources},
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_RESOURCES] == resources

        mock_setup.assert_called_once()
