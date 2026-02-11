"""Test the Ness Alarm config flow."""

from types import MappingProxyType
from unittest.mock import AsyncMock, patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.ness_alarm.const import (
    CONF_INFER_ARMING_STATE,
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


async def test_form_user(hass: HomeAssistant) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_client = AsyncMock()
    with (
        patch(
            "homeassistant.components.ness_alarm.config_flow.Client",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.ness_alarm.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 1992,
                CONF_INFER_ARMING_STATE: False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Ness Alarm 192.168.1.100:1992"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 1992,
        CONF_INFER_ARMING_STATE: False,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    mock_client.close.assert_awaited_once()


async def test_form_user_with_infer_arming_state(hass: HomeAssistant) -> None:
    """Test user form with infer_arming_state enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_client = AsyncMock()
    with (
        patch(
            "homeassistant.components.ness_alarm.config_flow.Client",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.ness_alarm.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 1992,
                CONF_INFER_ARMING_STATE: True,
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_INFER_ARMING_STATE] is True


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
        unique_id="192.168.1.100:1992",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
            CONF_INFER_ARMING_STATE: False,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_client = AsyncMock()
    mock_client.update.side_effect = OSError("Connection refused")
    with patch(
        "homeassistant.components.ness_alarm.config_flow.Client",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 1992,
                CONF_INFER_ARMING_STATE: False,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    mock_client.close.assert_awaited_once()


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_client = AsyncMock()
    mock_client.update.side_effect = RuntimeError("Unexpected")
    with patch(
        "homeassistant.components.ness_alarm.config_flow.Client",
        return_value=mock_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 1992,
                CONF_INFER_ARMING_STATE: False,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
    mock_client.close.assert_awaited_once()


async def test_import_yaml_config(hass: HomeAssistant) -> None:
    """Test importing YAML configuration."""
    with patch(
        "homeassistant.components.ness_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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
        await hass.async_block_till_done()

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


async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test we abort import if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.72",
            CONF_PORT: 4999,
        },
        unique_id="192.168.1.72:4999",
    )
    entry.add_to_hass(hass)

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
    assert result["reason"] == "already_configured"


async def test_zone_subentry_flow(hass: HomeAssistant) -> None:
    """Test adding a zone through subentry flow."""
    # Create main config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
        unique_id="192.168.1.100:1992",
    )
    entry.add_to_hass(hass)

    # Start zone subentry flow
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ZONE),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Configure zone
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_ZONE_NUMBER: 1,
            CONF_TYPE: BinarySensorDeviceClass.DOOR,
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Zone 1"
    assert result2["data"][CONF_ZONE_NUMBER] == 1
    assert result2["data"][CONF_TYPE] == BinarySensorDeviceClass.DOOR


async def test_zone_subentry_already_configured(hass: HomeAssistant) -> None:
    """Test adding a zone that already exists."""
    # Create main config entry with existing zone
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
        unique_id="192.168.1.100:1992",
    )
    entry.add_to_hass(hass)

    # Add existing zone subentry
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

    # Try to add the same zone again
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ZONE),
        context={"source": SOURCE_USER},
    )

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_ZONE_NUMBER: 1,
            CONF_TYPE: BinarySensorDeviceClass.DOOR,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_ZONE_NUMBER: "already_configured"}


async def test_zone_subentry_reconfigure(hass: HomeAssistant) -> None:
    """Test reconfiguring an existing zone."""
    # Create main config entry with a zone
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
        unique_id="192.168.1.100:1992",
    )
    entry.add_to_hass(hass)

    # Add zone subentry
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

    # Start reconfigure flow
    result = await entry.start_subentry_reconfigure_flow(hass, "zone_1_id")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"][CONF_ZONE_NUMBER] == "1"

    # Reconfigure zone type
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_TYPE: BinarySensorDeviceClass.DOOR,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
