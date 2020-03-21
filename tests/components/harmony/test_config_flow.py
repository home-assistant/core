"""Test the Logitech Harmony Hub config flow."""
from asynctest import CoroutineMock, MagicMock, patch

from homeassistant import config_entries, setup
from homeassistant.components.harmony.config_flow import CannotConnect
from homeassistant.components.harmony.const import DOMAIN


def _get_mock_harmonyapi(connect=None, close=None):
    harmonyapi_mock = MagicMock()
    type(harmonyapi_mock).connect = CoroutineMock(return_value=connect)
    type(harmonyapi_mock).close = CoroutineMock(return_value=close)

    return harmonyapi_mock


async def test_user_form(hass):
    """Test we get the user form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    harmonyapi = _get_mock_harmonyapi(connect=True)
    with patch(
        "homeassistant.components.harmony.config_flow.HarmonyAPI",
        return_value=harmonyapi,
    ), patch(
        "homeassistant.components.harmony.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.harmony.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.2.3.4", "name": "friend"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "friend"
    assert result2["data"] == {
        "host": "1.2.3.4",
        "name": "friend",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import(hass):
    """Test we get the form with import source."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    harmonyapi = _get_mock_harmonyapi(connect=True)
    with patch(
        "homeassistant.components.harmony.config_flow.HarmonyAPI",
        return_value=harmonyapi,
    ), patch(
        "homeassistant.components.harmony.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.harmony.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "1.2.3.4",
                "name": "friend",
                "activity": "Watch TV",
                "delay_secs": 0.9,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "friend"
    assert result["data"] == {
        "host": "1.2.3.4",
        "name": "friend",
        "activity": "Watch TV",
        "delay_secs": 0.9,
    }
    # It is not possible to import options at this time
    # so they end up in the config entry data and are
    # used a fallback when they are not in options
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_ssdp(hass):
    """Test we get the form with ssdp source."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            "friendlyName": "Harmony Hub",
            "ssdp_location": "http://192.168.209.238:8088/description",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] == {}

    harmonyapi = _get_mock_harmonyapi(connect=True)
    with patch(
        "homeassistant.components.harmony.config_flow.HarmonyAPI",
        return_value=harmonyapi,
    ), patch(
        "homeassistant.components.harmony.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.harmony.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Harmony Hub"
    assert result2["data"] == {
        "host": "192.168.209.238",
        "name": "Harmony Hub",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.harmony.config_flow.HarmonyAPI",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.2.3.4",
                "name": "friend",
                "activity": "Watch TV",
                "delay_secs": 0.2,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
