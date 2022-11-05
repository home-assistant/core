"""Test the lg_soundbar config flow."""
from __future__ import annotations

import socket
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.lg_soundbar.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from . import (
    MOCK_ENTITY_ID,
    TEMESCAL_ATTR_USERNAME,
    TEMESCAL_ATTR_UUID,
    TEMESCAL_MAC_INFO_DEV,
    TEMESCAL_PRODUCT_INFO,
    TEMESCAL_SPK_LIST_VIEW_INFO,
    setup_mock_temescal,
)

from tests.common import MockConfigEntry

MOCK_USERNAME = "name"


async def test_form(hass):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal, patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        setup_mock_temescal(
            hass=hass,
            mock_temescal=mock_temescal,
            msg_dicts={
                TEMESCAL_MAC_INFO_DEV: {TEMESCAL_ATTR_UUID: MOCK_ENTITY_ID},
                TEMESCAL_SPK_LIST_VIEW_INFO: {TEMESCAL_ATTR_USERNAME: MOCK_USERNAME},
            },
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == MOCK_USERNAME
    assert result2["result"].unique_id == MOCK_ENTITY_ID
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_mac_info_response_empty(hass):
    """Test we get the form, but response from the initial get_mac_info function call is empty."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal, patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        setup_mock_temescal(
            hass=hass,
            mock_temescal=mock_temescal,
            msg_dicts={
                TEMESCAL_MAC_INFO_DEV: {TEMESCAL_ATTR_UUID: MOCK_ENTITY_ID},
                TEMESCAL_SPK_LIST_VIEW_INFO: {TEMESCAL_ATTR_USERNAME: MOCK_USERNAME},
            },
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == MOCK_USERNAME
    assert result2["result"].unique_id == MOCK_ENTITY_ID
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_uuid_present_in_both_functions_uuid_q_empty(hass):
    """Get the form, uuid present in both get_mac_info and get_product_info calls.

    Value from get_mac_info is not added to uuid_q before get_product_info is run.
    """

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal, patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        setup_mock_temescal(
            hass=hass,
            mock_temescal=mock_temescal,
            msg_dicts={
                TEMESCAL_MAC_INFO_DEV: {TEMESCAL_ATTR_UUID: MOCK_ENTITY_ID},
                TEMESCAL_PRODUCT_INFO: {TEMESCAL_ATTR_UUID: MOCK_ENTITY_ID},
                TEMESCAL_SPK_LIST_VIEW_INFO: {TEMESCAL_ATTR_USERNAME: MOCK_USERNAME},
            },
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == MOCK_USERNAME
    assert result2["result"].unique_id == MOCK_ENTITY_ID
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_uuid_present_in_both_functions_uuid_q_not_empty(hass):
    """Get the form, uuid present in both get_mac_info and get_product_info calls.

    Value from get_mac_info is added to uuid_q before get_product_info is run.
    """

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.QUEUE_TIMEOUT",
        new=0.1,
    ), patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal, patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        setup_mock_temescal(
            hass=hass,
            mock_temescal=mock_temescal,
            msg_dicts={
                TEMESCAL_MAC_INFO_DEV: {TEMESCAL_ATTR_UUID: MOCK_ENTITY_ID},
                TEMESCAL_PRODUCT_INFO: {TEMESCAL_ATTR_UUID: MOCK_ENTITY_ID},
                TEMESCAL_SPK_LIST_VIEW_INFO: {TEMESCAL_ATTR_USERNAME: MOCK_USERNAME},
            },
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == MOCK_USERNAME
    assert result2["result"].unique_id == MOCK_ENTITY_ID
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_uuid_missing_from_mac_info(hass):
    """Test we get the form, but uuid is missing from the initial get_mac_info function call."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal, patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        setup_mock_temescal(
            hass=hass,
            mock_temescal=mock_temescal,
            msg_dicts={
                TEMESCAL_PRODUCT_INFO: {TEMESCAL_ATTR_UUID: MOCK_ENTITY_ID},
                TEMESCAL_SPK_LIST_VIEW_INFO: {TEMESCAL_ATTR_USERNAME: MOCK_USERNAME},
            },
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == MOCK_USERNAME
    assert result2["result"].unique_id == MOCK_ENTITY_ID
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_uuid_not_provided_by_api(hass):
    """Test we get the form, but uuid is missing from the all API messages."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.QUEUE_TIMEOUT",
        new=0.1,
    ), patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal, patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        setup_mock_temescal(
            hass=hass,
            mock_temescal=mock_temescal,
            msg_dicts={
                TEMESCAL_PRODUCT_INFO: {"i_model_no": "8", "i_model_type": 0},
                TEMESCAL_SPK_LIST_VIEW_INFO: {TEMESCAL_ATTR_USERNAME: MOCK_USERNAME},
            },
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == MOCK_USERNAME
    assert result2["result"].unique_id is None
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_both_queues_empty(hass):
    """Test we get the form, but none of the data we want is provided by the API."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.QUEUE_TIMEOUT",
        new=0.1,
    ), patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal, patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        setup_mock_temescal(hass=hass, mock_temescal=mock_temescal, msg_dicts={})

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "no_data"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_no_uuid_host_already_configured(hass):
    """Test we handle if the device has no UUID and the host has already been configured."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: DEFAULT_PORT,
        },
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.QUEUE_TIMEOUT",
        new=0.1,
    ), patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal:
        setup_mock_temescal(
            hass=hass,
            mock_temescal=mock_temescal,
            msg_dicts={
                TEMESCAL_SPK_LIST_VIEW_INFO: {TEMESCAL_ATTR_USERNAME: MOCK_USERNAME},
            },
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_form_socket_timeout(hass):
    """Test we handle socket.timeout error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal:
        mock_temescal.temescal.side_effect = socket.timeout
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_os_error(hass):
    """Test we handle OSError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal:
        mock_temescal.temescal.side_effect = OSError
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(hass):
    """Test we handle already configured error."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 0000,
        },
        unique_id=MOCK_ENTITY_ID,
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal:
        setup_mock_temescal(
            hass=hass,
            mock_temescal=mock_temescal,
            msg_dicts={
                TEMESCAL_MAC_INFO_DEV: {TEMESCAL_ATTR_UUID: MOCK_ENTITY_ID},
                TEMESCAL_SPK_LIST_VIEW_INFO: {TEMESCAL_ATTR_USERNAME: MOCK_USERNAME},
            },
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
