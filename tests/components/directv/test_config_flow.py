"""Test the DirecTV config flow."""
from typing import Any, Dict, Optional

from asynctest import patch
from requests.exceptions import RequestException

from homeassistant.components.directv.const import DOMAIN
from homeassistant.components.ssdp import ATTR_SSDP_LOCATION, ATTR_UPNP_SERIAL
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SOURCE
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.directv import (
    HOST,
    RECEIVER_ID,
    SSDP_LOCATION,
    UPNP_SERIAL,
    MockDirectvClass,
)


async def async_configure_flow(
    hass: HomeAssistantType, flow_id: str, user_input: Optional[Dict] = None
) -> Any:
    """Set up mock DirecTV integration flow."""
    with patch(
        "homeassistant.components.directv.config_flow.DIRECTV", new=MockDirectvClass,
    ):
        return await hass.config_entries.flow.async_configure(
            flow_id=flow_id, user_input=user_input
        )


async def async_init_flow(
    hass: HomeAssistantType,
    handler: str = DOMAIN,
    context: Optional[Dict] = None,
    data: Any = None,
) -> Any:
    """Set up mock DirecTV integration flow."""
    with patch(
        "homeassistant.components.directv.config_flow.DIRECTV", new=MockDirectvClass,
    ):
        return await hass.config_entries.flow.async_init(
            handler=handler, context=context, data=data
        )


async def test_duplicate_error(hass: HomeAssistantType) -> None:
    """Test that errors are shown when duplicates are added."""
    MockConfigEntry(
        domain=DOMAIN, unique_id=RECEIVER_ID, data={CONF_HOST: HOST}
    ).add_to_hass(hass)

    result = await async_init_flow(
        hass, context={CONF_SOURCE: SOURCE_IMPORT}, data={CONF_HOST: HOST}
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    result = await async_init_flow(
        hass, context={CONF_SOURCE: SOURCE_USER}, data={CONF_HOST: HOST}
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    result = await async_init_flow(
        hass,
        context={CONF_SOURCE: SOURCE_SSDP},
        data={ATTR_SSDP_LOCATION: SSDP_LOCATION, ATTR_UPNP_SERIAL: UPNP_SERIAL},
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_form(hass: HomeAssistantType) -> None:
    """Test we get the form."""
    await async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.directv.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.directv.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await async_configure_flow(hass, result["flow_id"], {CONF_HOST: HOST})

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {CONF_HOST: HOST}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistantType) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    with patch(
        "tests.components.directv.test_config_flow.MockDirectvClass.get_version",
        side_effect=RequestException,
    ) as mock_validate_input:
        result = await async_configure_flow(hass, result["flow_id"], {CONF_HOST: HOST},)

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await hass.async_block_till_done()
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_unknown_error(hass: HomeAssistantType) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    with patch(
        "tests.components.directv.test_config_flow.MockDirectvClass.get_version",
        side_effect=Exception,
    ) as mock_validate_input:
        result = await async_configure_flow(hass, result["flow_id"], {CONF_HOST: HOST},)

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"

    await hass.async_block_till_done()
    assert len(mock_validate_input.mock_calls) == 1


async def test_import(hass: HomeAssistantType) -> None:
    """Test the import step."""
    with patch(
        "homeassistant.components.directv.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.directv.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await async_init_flow(
            hass, context={CONF_SOURCE: SOURCE_IMPORT}, data={CONF_HOST: HOST},
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {CONF_HOST: HOST}

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_discovery(hass: HomeAssistantType) -> None:
    """Test the ssdp discovery step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data={ATTR_SSDP_LOCATION: SSDP_LOCATION, ATTR_UPNP_SERIAL: UPNP_SERIAL},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "ssdp_confirm"
    assert result["description_placeholders"] == {CONF_NAME: HOST}

    with patch(
        "homeassistant.components.directv.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.directv.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await async_configure_flow(hass, result["flow_id"], {})

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {CONF_HOST: HOST}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_discovery_confirm_abort(hass: HomeAssistantType) -> None:
    """Test we handle SSDP confirm cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data={ATTR_SSDP_LOCATION: SSDP_LOCATION, ATTR_UPNP_SERIAL: UPNP_SERIAL},
    )

    with patch(
        "tests.components.directv.test_config_flow.MockDirectvClass.get_version",
        side_effect=RequestException,
    ) as mock_validate_input:
        result = await async_configure_flow(hass, result["flow_id"], {})

    assert result["type"] == RESULT_TYPE_ABORT

    await hass.async_block_till_done()
    assert len(mock_validate_input.mock_calls) == 1


async def test_ssdp_discovery_confirm_unknown_error(hass: HomeAssistantType) -> None:
    """Test we handle SSDP confirm unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data={ATTR_SSDP_LOCATION: SSDP_LOCATION, ATTR_UPNP_SERIAL: UPNP_SERIAL},
    )

    with patch(
        "tests.components.directv.test_config_flow.MockDirectvClass.get_version",
        side_effect=Exception,
    ) as mock_validate_input:
        result = await async_configure_flow(hass, result["flow_id"], {})

    assert result["type"] == RESULT_TYPE_ABORT

    await hass.async_block_till_done()
    assert len(mock_validate_input.mock_calls) == 1
