"""Test APCUPSd setup process."""
from copy import copy
import logging
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.apcupsd import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_RESOURCES
from homeassistant.core import HomeAssistant

from . import MOCK_MINIMAL_STATUS, MOCK_STATUS

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create hass config_entry fixture."""

    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title=MOCK_STATUS["MODEL"],
        data={CONF_HOST: "test", CONF_PORT: 1234},
        options={},
        unique_id=MOCK_STATUS["SERIALNO"],
        source=config_entries.SOURCE_USER,
    )


async def test_flow_works(hass: HomeAssistant, config_entry: MockConfigEntry):
    """Test successful creation of config entries via user configuration."""
    with patch("apcaccess.status.parse") as mock_parse, patch(
        "apcaccess.status.get"
    ) as mock_get:
        mock_get.return_value = b""

        for status in (MOCK_STATUS, MOCK_MINIMAL_STATUS):
            mock_parse.return_value = status

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data=config_entry.data,
            )
            await hass.async_block_till_done()
            assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert result["title"] == status["MODEL"]
            assert result["data"][CONF_HOST] == config_entry.data[CONF_HOST]
            assert result["data"][CONF_PORT] == config_entry.data[CONF_PORT]
            assert result["description"] == "APCUPSd"


async def test_flow_import(hass: HomeAssistant, config_entry: MockConfigEntry):
    """Test successful creation of config entries via YAML import."""
    with patch("apcaccess.status.parse") as mock_parse, patch(
        "apcaccess.status.get"
    ) as mock_get:
        mock_get.return_value = b""

        for status in (MOCK_STATUS, MOCK_MINIMAL_STATUS):
            mock_parse.return_value = status

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=config_entry.data,
            )
            await hass.async_block_till_done()
            assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert result["title"] == status["MODEL"]
            assert result["data"][CONF_HOST] == config_entry.data[CONF_HOST]
            assert result["data"][CONF_PORT] == config_entry.data[CONF_PORT]
            assert result["description"] == "APCUPSd"


async def test_config_flow_cannot_connect(hass: HomeAssistant):
    """Test config flow setup with connection error."""
    with patch("apcaccess.status.get") as mock_get:
        mock_get.side_effect = OSError()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"]["base"] == "cannot_connect"


async def test_config_flow_no_status(hass: HomeAssistant):
    """Test config flow setup with successful connection but no status is reported."""
    with patch("apcaccess.status.parse") as mock_parse, patch(
        "apcaccess.status.get"
    ) as mock_get:
        mock_get.return_value = b""
        mock_parse.return_value = None

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "no_status"


async def test_config_flow_duplicate(
    hass: HomeAssistant, config_entry: MockConfigEntry
):
    """Test config flow setup with duplicate integration."""
    # Add a duplicate integration.
    with patch("apcaccess.status.parse") as mock_parse, patch(
        "apcaccess.status.get"
    ) as mock_get:
        mock_get.return_value = b""
        mock_parse.return_value = MOCK_STATUS

        # Add a config entry.
        config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=config_entry.data,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"

        # Now we change the serial number and add it again.
        another_device_status = copy(MOCK_STATUS)
        another_device_status["SERIALNO"] = "ZZZZZZZZZ"
        mock_parse.return_value = another_device_status

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=config_entry.data,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == config_entry.data
        assert result["title"] == MOCK_STATUS["MODEL"]
        assert result["description"] == "APCUPSd"


async def test_options_flow(hass: HomeAssistant, config_entry: MockConfigEntry, caplog):
    """Test options flow."""
    with patch("apcaccess.status.parse") as mock_parse, patch(
        "apcaccess.status.get"
    ) as mock_get:
        mock_get.return_value = b""
        mock_parse.return_value = MOCK_STATUS
        config_entry.add_to_hass(hass)
        await config_entry.async_setup(hass)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert CONF_RESOURCES in result["data_schema"]({})
        resources = result["data_schema"]({})[CONF_RESOURCES]

        # The underlying library apcaccess would report undocumented extra fields that are not supported by HA
        # for some model, so the available resources are actually a subset of the reported MOCK_STATUS.
        assert all(resource in MOCK_STATUS for resource in resources)

        # Now deselect one resource and submit.
        resources.remove("LOADPCT")
        result = await hass.config_entries.options.async_init(
            config_entry.entry_id, data={CONF_RESOURCES: resources}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert (
            hass.config_entries.async_get_entry(config_entry.entry_id).options[
                CONF_RESOURCES
            ]
            == resources
        )

        # Now give an unavailable but valid resource "REG1" to options
        with caplog.at_level(logging.WARNING):
            result = await hass.config_entries.options.async_init(
                config_entry.entry_id, data={CONF_RESOURCES: resources + ["REG1"]}
            )
            assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert (
                hass.config_entries.async_get_entry(config_entry.entry_id).options[
                    CONF_RESOURCES
                ]
                == resources
            )
        assert "REG1" in caplog.text
