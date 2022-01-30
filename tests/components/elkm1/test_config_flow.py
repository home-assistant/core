"""Test the Elk-M1 Control config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.elkm1.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from . import MOCK_MAC, _patch_discovery, _patch_elk, mock_elk


async def test_form_user_with_secure_elk_no_discovery(hass):
    """Test we can setup a secure elk."""

    with _patch_discovery(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "manual_connection"

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_discovery(no_device=True), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "secure",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "test-password",
                "temperature_unit": "°F",
                "prefix": "",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elks://1.2.3.4",
        "password": "test-password",
        "prefix": "",
        "temperature_unit": "°F",
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_secure_elk_with_discovery(hass):
    """Test we can setup a secure elk."""

    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] is None
    assert result["step_id"] == "user"

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_elk(elk=mocked_elk):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device": MOCK_MAC},
        )
        await hass.async_block_till_done()

    with _patch_discovery(), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "temperature_unit": "°F",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "ElkM1 ddeeff"
    assert result3["data"] == {
        "auto_configure": True,
        "host": "elks://127.0.0.1:2601",
        "password": "test-password",
        "prefix": "",
        "temperature_unit": "°F",
        "username": "test-username",
    }
    assert result3["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_secure_elk_with_discovery_pick_manual(hass):
    """Test we can setup a secure elk with discovery but user picks manual."""

    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] is None
    assert result["step_id"] == "user"

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_elk(elk=mocked_elk):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device": None},
        )
        await hass.async_block_till_done()

    with _patch_discovery(), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "protocol": "secure",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "test-password",
                "temperature_unit": "°F",
                "prefix": "",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "ElkM1"
    assert result3["data"] == {
        "auto_configure": True,
        "host": "elks://1.2.3.4",
        "password": "test-password",
        "prefix": "",
        "temperature_unit": "°F",
        "username": "test-username",
    }
    assert result3["result"].unique_id is None
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_tls_elk_no_discovery(hass):
    """Test we can setup a secure elk."""

    with _patch_discovery(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "manual_connection"

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_discovery(no_device=True), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "TLS 1.2",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "test-password",
                "temperature_unit": "°F",
                "prefix": "",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elksv1_2://1.2.3.4",
        "password": "test-password",
        "prefix": "",
        "temperature_unit": "°F",
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_non_secure_elk_no_discovery(hass):
    """Test we can setup a non-secure elk."""

    with _patch_discovery(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "manual_connection"

    mocked_elk = mock_elk(invalid_auth=None, sync_complete=True)

    with _patch_discovery(no_device=True), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "non-secure",
                "address": "1.2.3.4",
                "temperature_unit": "°F",
                "prefix": "guest_house",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "guest_house"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elk://1.2.3.4",
        "prefix": "guest_house",
        "username": "",
        "password": "",
        "temperature_unit": "°F",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_serial_elk_no_discovery(hass):
    """Test we can setup a serial elk."""

    with _patch_discovery(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "manual_connection"

    mocked_elk = mock_elk(invalid_auth=None, sync_complete=True)

    with _patch_discovery(no_device=True), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "serial",
                "address": "/dev/ttyS0:115200",
                "temperature_unit": "°C",
                "prefix": "",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "serial:///dev/ttyS0:115200",
        "prefix": "",
        "username": "",
        "password": "",
        "temperature_unit": "°C",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    with _patch_discovery(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    mocked_elk = mock_elk(invalid_auth=None, sync_complete=None)

    with _patch_discovery(no_device=True), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.config_flow.VALIDATE_TIMEOUT",
        0,
    ), patch(
        "homeassistant.components.elkm1.config_flow.LOGIN_TIMEOUT",
        0,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "secure",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "test-password",
                "temperature_unit": "°F",
                "prefix": "",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_HOST: "cannot_connect"}


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mocked_elk = mock_elk(invalid_auth=True, sync_complete=True)

    with patch(
        "homeassistant.components.elkm1.config_flow.elkm1.Elk",
        return_value=mocked_elk,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "secure",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "test-password",
                "temperature_unit": "°F",
                "prefix": "",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_PASSWORD: "invalid_auth"}


async def test_form_import(hass):
    """Test we get the form with import source."""

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)
    with _patch_discovery(no_device=True), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
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
        await hass.async_block_till_done()

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
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
