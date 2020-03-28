"""Test the Elk-M1 Control config flow."""

from asynctest import CoroutineMock, MagicMock, PropertyMock, patch

from homeassistant import config_entries, setup
from homeassistant.components.elkm1.const import DOMAIN


def mock_elk(invalid_auth=None, sync_complete=None):
    """Mock m1lib Elk."""
    mocked_elk = MagicMock()
    type(mocked_elk).invalid_auth = PropertyMock(return_value=invalid_auth)
    type(mocked_elk).sync_complete = CoroutineMock()
    return mocked_elk


async def test_form_user_with_secure_elk(hass):
    """Test we can setup a secure elk."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mocked_elk = mock_elk(invalid_auth=False)

    with patch(
        "homeassistant.components.elkm1.config_flow.elkm1.Elk", return_value=mocked_elk,
    ), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "secure",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "test-password",
                "temperature_unit": "F",
                "prefix": "",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elks://1.2.3.4",
        "password": "test-password",
        "prefix": "",
        "temperature_unit": "F",
        "username": "test-username",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_non_secure_elk(hass):
    """Test we can setup a non-secure elk."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mocked_elk = mock_elk(invalid_auth=False)

    with patch(
        "homeassistant.components.elkm1.config_flow.elkm1.Elk", return_value=mocked_elk,
    ), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "non-secure",
                "address": "1.2.3.4",
                "temperature_unit": "F",
                "prefix": "guest_house",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "guest_house"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elk://1.2.3.4",
        "prefix": "guest_house",
        "username": "",
        "password": "",
        "temperature_unit": "F",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_serial_elk(hass):
    """Test we can setup a serial elk."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mocked_elk = mock_elk(invalid_auth=False)

    with patch(
        "homeassistant.components.elkm1.config_flow.elkm1.Elk", return_value=mocked_elk,
    ), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "serial",
                "address": "/dev/ttyS0:115200",
                "temperature_unit": "F",
                "prefix": "",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "serial:///dev/ttyS0:115200",
        "prefix": "",
        "username": "",
        "password": "",
        "temperature_unit": "F",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mocked_elk = mock_elk(invalid_auth=False)

    with patch(
        "homeassistant.components.elkm1.config_flow.elkm1.Elk", return_value=mocked_elk,
    ), patch(
        "homeassistant.components.elkm1.config_flow.async_wait_for_elk_to_sync",
        return_value=False,
    ):  # async_wait_for_elk_to_sync is being patched to avoid making the test wait 45s
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "secure",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "test-password",
                "temperature_unit": "F",
                "prefix": "",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mocked_elk = mock_elk(invalid_auth=True)

    with patch(
        "homeassistant.components.elkm1.config_flow.elkm1.Elk", return_value=mocked_elk,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "secure",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "test-password",
                "temperature_unit": "F",
                "prefix": "",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_import(hass):
    """Test we get the form with import source."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    mocked_elk = mock_elk(invalid_auth=False)
    with patch(
        "homeassistant.components.elkm1.config_flow.elkm1.Elk", return_value=mocked_elk,
    ), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "elks://1.2.3.4",
                "username": "friend",
                "password": "love",
                "temperature_unit": "C",
                "auto_configure": False,
                "keypad": {
                    "enabled": True,
                    "exclude": [],
                    "include": [[1, 1], [2, 2], [3, 3]],
                },
                "output": {"enabled": False, "exclude": [], "include": []},
                "counter": {"enabled": False, "exclude": [], "include": []},
                "plc": {"enabled": False, "exclude": [], "include": []},
                "prefix": "ohana",
                "setting": {"enabled": False, "exclude": [], "include": []},
                "area": {"enabled": False, "exclude": [], "include": []},
                "task": {"enabled": False, "exclude": [], "include": []},
                "thermostat": {"enabled": False, "exclude": [], "include": []},
                "zone": {
                    "enabled": True,
                    "exclude": [[15, 15], [28, 208]],
                    "include": [],
                },
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "ohana"

    assert result["data"] == {
        "auto_configure": False,
        "host": "elks://1.2.3.4",
        "keypad": {"enabled": True, "exclude": [], "include": [[1, 1], [2, 2], [3, 3]]},
        "output": {"enabled": False, "exclude": [], "include": []},
        "password": "love",
        "plc": {"enabled": False, "exclude": [], "include": []},
        "prefix": "ohana",
        "setting": {"enabled": False, "exclude": [], "include": []},
        "area": {"enabled": False, "exclude": [], "include": []},
        "counter": {"enabled": False, "exclude": [], "include": []},
        "task": {"enabled": False, "exclude": [], "include": []},
        "temperature_unit": "C",
        "thermostat": {"enabled": False, "exclude": [], "include": []},
        "username": "friend",
        "zone": {"enabled": True, "exclude": [[15, 15], [28, 208]], "include": []},
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
