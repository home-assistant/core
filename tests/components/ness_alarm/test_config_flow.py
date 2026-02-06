"""Test the Ness Alarm config flow."""

from unittest.mock import patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.ness_alarm.const import (
    CONF_INFER_ARMING_STATE,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
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

    with patch(
        "homeassistant.components.ness_alarm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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


async def test_form_user_with_infer_arming_state(hass: HomeAssistant) -> None:
    """Test user form with infer_arming_state enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ness_alarm.async_setup_entry",
        return_value=True,
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
