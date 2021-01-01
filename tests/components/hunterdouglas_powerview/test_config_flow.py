"""Test the Logitech Harmony Hub config flow."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries, setup
from homeassistant.components.hunterdouglas_powerview.const import DOMAIN

from tests.common import MockConfigEntry, load_fixture


def _get_mock_powerview_userdata(userdata=None, get_resources=None):
    mock_powerview_userdata = MagicMock()
    if not userdata:
        userdata = json.loads(load_fixture("hunterdouglas_powerview/userdata.json"))
    if get_resources:
        type(mock_powerview_userdata).get_resources = AsyncMock(
            side_effect=get_resources
        )
    else:
        type(mock_powerview_userdata).get_resources = AsyncMock(return_value=userdata)
    return mock_powerview_userdata


async def test_user_form(hass):
    """Test we get the user form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_powerview_userdata = _get_mock_powerview_userdata()
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.hunterdouglas_powerview.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.2.3.4"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "AlexanderHD"
    assert result2["data"] == {
        "host": "1.2.3.4",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result3["type"] == "form"
    assert result3["errors"] == {}

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {"host": "1.2.3.4"},
    )
    assert result4["type"] == "abort"


async def test_form_import(hass):
    """Test we get the form with import source."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    mock_powerview_userdata = _get_mock_powerview_userdata()
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.hunterdouglas_powerview.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": "1.2.3.4"},
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "AlexanderHD"
    assert result["data"] == {
        "host": "1.2.3.4",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_homekit(hass):
    """Test we get the form with homekit source."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    ignored_config_entry = MockConfigEntry(domain=DOMAIN, data={}, source="ignore")
    ignored_config_entry.add_to_hass(hass)

    mock_powerview_userdata = _get_mock_powerview_userdata()
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "homekit"},
            data={
                "host": "1.2.3.4",
                "properties": {"id": "AA::BB::CC::DD::EE::FF"},
                "name": "PowerViewHub._hap._tcp.local.",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] is None
    assert result["description_placeholders"] == {
        "host": "1.2.3.4",
        "name": "PowerViewHub",
    }

    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ), patch(
        "homeassistant.components.hunterdouglas_powerview.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.hunterdouglas_powerview.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "PowerViewHub"
    assert result2["data"] == {"host": "1.2.3.4"}
    assert result2["result"].unique_id == "ABC123"

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "homekit"},
        data={
            "host": "1.2.3.4",
            "properties": {"id": "AA::BB::CC::DD::EE::FF"},
            "name": "PowerViewHub._hap._tcp.local.",
        },
    )
    assert result3["type"] == "abort"


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerview_userdata = _get_mock_powerview_userdata(
        get_resources=asyncio.TimeoutError
    )
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.2.3.4"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_no_data(hass):
    """Test we handle no data being returned from the hub."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerview_userdata = _get_mock_powerview_userdata(userdata={"userData": {}})
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.2.3.4"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_unknown_exception(hass):
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerview_userdata = _get_mock_powerview_userdata(userdata={"userData": {}})
    with patch(
        "homeassistant.components.hunterdouglas_powerview.UserData",
        return_value=mock_powerview_userdata,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.2.3.4"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
