"""Test the Ness Alarm config flow."""

from types import MappingProxyType
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.ness_alarm.const import (
    CONF_INFER_ARMING_STATE,
    CONF_SHOW_HOME_MODE,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    DOMAIN,
    SUBENTRY_TYPE_ZONE,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, ConfigSubentry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
            CONF_INFER_ARMING_STATE: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ness Alarm 192.168.1.100:1992"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 1992,
        CONF_INFER_ARMING_STATE: False,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    mock_client.close.assert_awaited_once()


async def test_user_flow_with_infer_arming_state(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow with infer_arming_state enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
            CONF_INFER_ARMING_STATE: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_INFER_ARMING_STATE] is True


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
            CONF_INFER_ARMING_STATE: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (OSError("Connection refused"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (RuntimeError("Unexpected"), "unknown"),
    ],
)
async def test_user_flow_connection_error_recovery(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test connection error handling and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # First attempt fails
    mock_client.update.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
            CONF_INFER_ARMING_STATE: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    mock_client.close.assert_awaited_once()

    # Second attempt succeeds
    mock_client.update.side_effect = None
    mock_client.close.reset_mock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
            CONF_INFER_ARMING_STATE: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_import_yaml_config(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test importing YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.1.72",
            CONF_PORT: 4999,
            CONF_INFER_ARMING_STATE: False,
            CONF_ZONES: [
                {CONF_ZONE_NAME: "Garage", CONF_ZONE_ID: 1},
                {
                    CONF_ZONE_NAME: "Front Door",
                    CONF_ZONE_ID: 5,
                    CONF_ZONE_TYPE: BinarySensorDeviceClass.DOOR,
                },
            ],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ness Alarm 192.168.1.72:4999"
    assert result["data"] == {
        CONF_HOST: "192.168.1.72",
        CONF_PORT: 4999,
        CONF_INFER_ARMING_STATE: False,
    }

    # Check that subentries were created for zones with names preserved
    assert len(result["subentries"]) == 2
    assert result["subentries"][0]["title"] == "Zone 1"
    assert result["subentries"][0]["unique_id"] == "zone_1"
    assert result["subentries"][0]["data"][CONF_TYPE] == BinarySensorDeviceClass.MOTION
    assert result["subentries"][0]["data"][CONF_ZONE_NAME] == "Garage"
    assert result["subentries"][1]["title"] == "Zone 5"
    assert result["subentries"][1]["unique_id"] == "zone_5"
    assert result["subentries"][1]["data"][CONF_TYPE] == BinarySensorDeviceClass.DOOR
    assert result["subentries"][1]["data"][CONF_ZONE_NAME] == "Front Door"

    assert len(mock_setup_entry.mock_calls) == 1
    mock_client.close.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        (OSError("Connection refused"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (RuntimeError("Unexpected"), "unknown"),
    ],
)
async def test_import_yaml_config_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    expected_reason: str,
) -> None:
    """Test importing YAML configuration."""
    mock_client.update.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.1.72",
            CONF_PORT: 4999,
            CONF_INFER_ARMING_STATE: False,
            CONF_ZONES: [
                {CONF_ZONE_NAME: "Garage", CONF_ZONE_ID: 1},
                {
                    CONF_ZONE_NAME: "Front Door",
                    CONF_ZONE_ID: 5,
                    CONF_ZONE_TYPE: BinarySensorDeviceClass.DOOR,
                },
            ],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


async def test_import_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort import if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 4999,
            CONF_ZONES: [],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        (OSError("Connection refused"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (RuntimeError("Unexpected"), "unknown"),
    ],
)
async def test_import_connection_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    side_effect: Exception,
    expected_reason: str,
) -> None:
    """Test import aborts on connection errors."""
    mock_client.update.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.1.72",
            CONF_PORT: 4999,
            CONF_ZONES: [],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    mock_client.close.assert_awaited_once()


async def test_zone_subentry_flow(hass: HomeAssistant) -> None:
    """Test adding a zone through subentry flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ZONE),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_ZONE_NUMBER: 1,
            CONF_TYPE: BinarySensorDeviceClass.DOOR,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Zone 1"
    assert result["data"][CONF_ZONE_NUMBER] == 1
    assert result["data"][CONF_TYPE] == BinarySensorDeviceClass.DOOR


async def test_zone_subentry_already_configured(hass: HomeAssistant) -> None:
    """Test adding a zone that already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)

    entry.subentries = {
        "zone_1_id": ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_ZONE,
            subentry_id="zone_1_id",
            unique_id="zone_1",
            title="Zone 1",
            data=MappingProxyType(
                {
                    CONF_ZONE_NUMBER: 1,
                    CONF_TYPE: BinarySensorDeviceClass.MOTION,
                }
            ),
        )
    }

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ZONE),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_ZONE_NUMBER: 1,
            CONF_TYPE: BinarySensorDeviceClass.DOOR,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ZONE_NUMBER: "already_configured"}


async def test_zone_subentry_reconfigure(hass: HomeAssistant) -> None:
    """Test reconfiguring an existing zone."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)

    zone_subentry = ConfigSubentry(
        subentry_type=SUBENTRY_TYPE_ZONE,
        subentry_id="zone_1_id",
        unique_id="zone_1",
        title="Zone 1",
        data=MappingProxyType(
            {
                CONF_ZONE_NUMBER: 1,
                CONF_TYPE: BinarySensorDeviceClass.MOTION,
            }
        ),
    )
    entry.subentries = {"zone_1_id": zone_subentry}

    result = await entry.start_subentry_reconfigure_flow(hass, "zone_1_id")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"][CONF_ZONE_NUMBER] == "1"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_TYPE: BinarySensorDeviceClass.DOOR,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow to configure alarm panel settings."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SHOW_HOME_MODE: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SHOW_HOME_MODE] is False


async def test_options_flow_enable_home_mode(hass: HomeAssistant) -> None:
    """Test options flow to enable home mode."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
        options={CONF_SHOW_HOME_MODE: False},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SHOW_HOME_MODE: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SHOW_HOME_MODE] is True
