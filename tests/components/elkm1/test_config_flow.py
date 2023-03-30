"""Test the Elk-M1 Control config flow."""
from dataclasses import asdict
from unittest.mock import patch

from elkm1_lib.discovery import ElkSystem
import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.elkm1.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    ELK_DISCOVERY,
    ELK_DISCOVERY_NON_STANDARD_PORT,
    ELK_NON_SECURE_DISCOVERY,
    MOCK_IP_ADDRESS,
    MOCK_MAC,
    _patch_discovery,
    _patch_elk,
    mock_elk,
)

from tests.common import MockConfigEntry

DHCP_DISCOVERY = dhcp.DhcpServiceInfo(MOCK_IP_ADDRESS, "", MOCK_MAC)
ELK_DISCOVERY_INFO = asdict(ELK_DISCOVERY)
ELK_DISCOVERY_INFO_NON_STANDARD_PORT = asdict(ELK_DISCOVERY_NON_STANDARD_PORT)

MODULE = "homeassistant.components.elkm1"


async def test_discovery_ignored_entry(hass: HomeAssistant) -> None:
    """Test we abort on ignored entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"elks://{MOCK_IP_ADDRESS}"},
        unique_id="aa:bb:cc:dd:ee:ff",
        source=config_entries.SOURCE_IGNORE,
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=ELK_DISCOVERY_INFO,
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_user_with_secure_elk_no_discovery(hass: HomeAssistant) -> None:
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
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_insecure_elk_skip_discovery(hass: HomeAssistant) -> None:
    """Test we can setup a insecure elk with skipping discovery."""

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    with _patch_discovery(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "manual_connection"

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_discovery(), _patch_elk(elk=mocked_elk), patch(
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
                "username": "test-username",
                "password": "test-password",
                "prefix": "",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elk://1.2.3.4",
        "password": "test-password",
        "prefix": "",
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_insecure_elk_no_discovery(hass: HomeAssistant) -> None:
    """Test we can setup a insecure elk."""

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

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
                "protocol": "non-secure",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "test-password",
                "prefix": "",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elk://1.2.3.4",
        "password": "test-password",
        "prefix": "",
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_insecure_elk_times_out(hass: HomeAssistant) -> None:
    """Test we can setup a insecure elk that times out."""

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    with _patch_discovery(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "manual_connection"

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=False)

    with patch(
        "homeassistant.components.elkm1.config_flow.VALIDATE_TIMEOUT",
        0,
    ), patch(
        "homeassistant.components.elkm1.config_flow.LOGIN_TIMEOUT", 0
    ), _patch_discovery(), _patch_elk(
        elk=mocked_elk
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "non-secure",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "test-password",
                "prefix": "",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_user_with_secure_elk_no_discovery_ip_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test we abort when we try to configure the same ip."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"elks://{MOCK_IP_ADDRESS}"},
        unique_id="cc:cc:cc:cc:cc:cc",
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "manual_connection"

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_discovery(no_device=True), _patch_elk(elk=mocked_elk):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "secure",
                "address": "127.0.0.1",
                "username": "test-username",
                "password": "test-password",
                "prefix": "",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "address_already_configured"


async def test_form_user_with_secure_elk_with_discovery(hass: HomeAssistant) -> None:
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
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "ElkM1 ddeeff"
    assert result3["data"] == {
        "auto_configure": True,
        "host": "elks://127.0.0.1",
        "password": "test-password",
        "prefix": "",
        "username": "test-username",
    }
    assert result3["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_secure_elk_with_discovery_pick_manual(
    hass: HomeAssistant,
) -> None:
    """Test we can setup a secure elk with discovery but user picks manual and directed discovery fails."""

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
        "username": "test-username",
    }
    assert result3["result"].unique_id is None
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_secure_elk_with_discovery_pick_manual_direct_discovery(
    hass: HomeAssistant,
) -> None:
    """Test we can setup a secure elk with discovery but user picks manual and directed discovery succeeds."""

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
                "address": "127.0.0.1",
                "username": "test-username",
                "password": "test-password",
                "prefix": "",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "ElkM1 ddeeff"
    assert result3["data"] == {
        "auto_configure": True,
        "host": "elks://127.0.0.1",
        "password": "test-password",
        "prefix": "",
        "username": "test-username",
    }
    assert result3["result"].unique_id == MOCK_MAC
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_tls_elk_no_discovery(hass: HomeAssistant) -> None:
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
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_non_secure_elk_no_discovery(hass: HomeAssistant) -> None:
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
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_with_serial_elk_no_discovery(hass: HomeAssistant) -> None:
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
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
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
                "prefix": "",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle an unknown exception during connecting."""
    with _patch_discovery(no_device=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    mocked_elk = mock_elk(invalid_auth=None, sync_complete=None, exception=OSError)

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
                "prefix": "",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mocked_elk = mock_elk(invalid_auth=True, sync_complete=True)

    with patch(
        "homeassistant.components.elkm1.config_flow.Elk",
        return_value=mocked_elk,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "secure",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "test-password",
                "prefix": "",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_PASSWORD: "invalid_auth"}


async def test_form_invalid_auth_no_password(hass: HomeAssistant) -> None:
    """Test we handle invalid auth error when no password is provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mocked_elk = mock_elk(invalid_auth=True, sync_complete=True)

    with patch(
        "homeassistant.components.elkm1.config_flow.Elk",
        return_value=mocked_elk,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "secure",
                "address": "1.2.3.4",
                "username": "test-username",
                "password": "",
                "prefix": "",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_PASSWORD: "invalid_auth"}


async def test_form_import(hass: HomeAssistant) -> None:
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


async def test_form_import_device_discovered(hass: HomeAssistant) -> None:
    """Test we can import with discovery."""

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)
    with _patch_discovery(), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "elks://127.0.0.1",
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
    assert result["result"].unique_id == MOCK_MAC
    assert result["data"] == {
        "auto_configure": False,
        "host": "elks://127.0.0.1",
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


async def test_form_import_non_secure_device_discovered(hass: HomeAssistant) -> None:
    """Test we can import non-secure with discovery."""

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)
    with _patch_discovery(), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "elk://127.0.0.1:2101",
                "username": "",
                "password": "",
                "auto_configure": True,
                "prefix": "ohana",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "ohana"
    assert result["result"].unique_id == MOCK_MAC
    assert result["data"] == {
        "auto_configure": True,
        "host": "elk://127.0.0.1:2101",
        "password": "",
        "prefix": "ohana",
        "username": "",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import_non_secure_non_stanadard_port_device_discovered(
    hass: HomeAssistant,
) -> None:
    """Test we can import non-secure non standard port with discovery."""

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)
    with _patch_discovery(), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "elk://127.0.0.1:444",
                "username": "",
                "password": "",
                "auto_configure": True,
                "prefix": "ohana",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "ohana"
    assert result["result"].unique_id == MOCK_MAC
    assert result["data"] == {
        "auto_configure": True,
        "host": "elk://127.0.0.1:444",
        "password": "",
        "prefix": "ohana",
        "username": "",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import_non_secure_device_discovered_invalid_auth(
    hass: HomeAssistant,
) -> None:
    """Test we abort import with invalid auth."""

    mocked_elk = mock_elk(invalid_auth=True, sync_complete=False)
    with _patch_discovery(), _patch_elk(elk=mocked_elk):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "elks://127.0.0.1",
                "username": "invalid",
                "password": "",
                "auto_configure": False,
                "prefix": "ohana",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "invalid_auth"


async def test_form_import_existing(hass: HomeAssistant) -> None:
    """Test we abort on existing import."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"elks://{MOCK_IP_ADDRESS}"},
        unique_id="cc:cc:cc:cc:cc:cc",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "host": f"elks://{MOCK_IP_ADDRESS}",
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

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "address_already_configured"


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_INTEGRATION_DISCOVERY, ELK_DISCOVERY_INFO),
    ],
)
async def test_discovered_by_dhcp_or_discovery_mac_address_mismatch_host_already_configured(
    hass: HomeAssistant, source, data
) -> None:
    """Test we abort if the host is already configured but the mac does not match."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"elks://{MOCK_IP_ADDRESS}"},
        unique_id="cc:cc:cc:cc:cc:cc",
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == "cc:cc:cc:cc:cc:cc"


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_INTEGRATION_DISCOVERY, ELK_DISCOVERY_INFO),
    ],
)
async def test_discovered_by_dhcp_or_discovery_adds_missing_unique_id(
    hass: HomeAssistant, source, data
) -> None:
    """Test we add a missing unique id to the config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"elks://{MOCK_IP_ADDRESS}"},
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == MOCK_MAC


async def test_discovered_by_discovery_and_dhcp(hass: HomeAssistant) -> None:
    """Test we get the form with discovery and abort for dhcp source when we get both."""

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=ELK_DISCOVERY_INFO,
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with _patch_discovery(), _patch_elk():
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"

    with _patch_discovery(), _patch_elk():
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                hostname="any",
                ip=MOCK_IP_ADDRESS,
                macaddress="00:00:00:00:00:00",
            ),
        )
        await hass.async_block_till_done()
    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "already_in_progress"


async def test_discovered_by_discovery(hass: HomeAssistant) -> None:
    """Test we can setup when discovered from discovery."""

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=ELK_DISCOVERY_INFO,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovered_connection"
    assert result["errors"] == {}

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_discovery(), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1 ddeeff"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elks://127.0.0.1",
        "password": "test-password",
        "prefix": "",
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovered_by_discovery_non_standard_port(hass: HomeAssistant) -> None:
    """Test we can setup when discovered from discovery with a non-standard port."""

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=ELK_DISCOVERY_INFO_NON_STANDARD_PORT,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovered_connection"
    assert result["errors"] == {}

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_discovery(), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1 ddeeff"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elks://127.0.0.1:444",
        "password": "test-password",
        "prefix": "",
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovered_by_discovery_url_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test we abort when we discover a device that is already setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"elks://{MOCK_IP_ADDRESS}"},
        unique_id="cc:cc:cc:cc:cc:cc",
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=ELK_DISCOVERY_INFO,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovered_by_dhcp_udp_responds(hass: HomeAssistant) -> None:
    """Test we can setup when discovered from dhcp but with udp response."""

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovered_connection"
    assert result["errors"] == {}

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_discovery(), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1 ddeeff"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elks://127.0.0.1",
        "password": "test-password",
        "prefix": "",
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovered_by_dhcp_udp_responds_with_nonsecure_port(
    hass: HomeAssistant,
) -> None:
    """Test we can setup when discovered from dhcp but with udp response using the non-secure port."""

    with _patch_discovery(device=ELK_NON_SECURE_DISCOVERY), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovered_connection"
    assert result["errors"] == {}

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_discovery(device=ELK_NON_SECURE_DISCOVERY), _patch_elk(
        elk=mocked_elk
    ), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "non-secure",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1 ddeeff"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elk://127.0.0.1",
        "password": "",
        "prefix": "",
        "username": "",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovered_by_dhcp_udp_responds_existing_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test we can setup when discovered from dhcp but with udp response with an existing config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "elks://6.6.6.6"},
        unique_id="cc:cc:cc:cc:cc:cc",
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery(), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovered_connection"
    assert result["errors"] == {}

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_discovery(), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ElkM1 ddeeff"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elks://127.0.0.1",
        "password": "test-password",
        "prefix": "ddeeff",
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 2


async def test_discovered_by_dhcp_no_udp_response(hass: HomeAssistant) -> None:
    """Test we can setup when discovered from dhcp but no udp response."""

    with _patch_discovery(no_device=True), _patch_elk():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=DHCP_DISCOVERY
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_multiple_instances_with_discovery(hass: HomeAssistant) -> None:
    """Test we can setup a secure elk."""

    elk_discovery_1 = ElkSystem("aa:bb:cc:dd:ee:ff", "127.0.0.1", 2601)
    elk_discovery_2 = ElkSystem("aa:bb:cc:dd:ee:fe", "127.0.0.2", 2601)

    with _patch_discovery(device=elk_discovery_1):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert not result["errors"]
    assert result["step_id"] == "user"

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_elk(elk=mocked_elk):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device": elk_discovery_1.mac_address},
        )
        await hass.async_block_till_done()

    with _patch_discovery(device=elk_discovery_1), _patch_elk(elk=mocked_elk), patch(
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
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "ElkM1 ddeeff"
    assert result3["data"] == {
        "auto_configure": True,
        "host": "elks://127.0.0.1",
        "password": "test-password",
        "prefix": "",
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    # Now try to add another instance with the different discovery info
    with _patch_discovery(device=elk_discovery_2):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert not result["errors"]
    assert result["step_id"] == "user"

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_elk(elk=mocked_elk):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device": elk_discovery_2.mac_address},
        )
        await hass.async_block_till_done()

    with _patch_discovery(device=elk_discovery_2), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "ElkM1 ddeefe"
    assert result3["data"] == {
        "auto_configure": True,
        "host": "elks://127.0.0.2",
        "password": "test-password",
        "prefix": "ddeefe",
        "username": "test-username",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # Finally, try to add another instance manually with no discovery info

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
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "non-secure",
                "address": "1.2.3.4",
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
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_multiple_instances_with_tls_v12(hass: HomeAssistant) -> None:
    """Test we can setup a secure elk with tls v1_2."""

    elk_discovery_1 = ElkSystem("aa:bb:cc:dd:ee:ff", "127.0.0.1", 2601)
    elk_discovery_2 = ElkSystem("aa:bb:cc:dd:ee:fe", "127.0.0.2", 2601)

    with _patch_discovery(device=elk_discovery_1):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert not result["errors"]
    assert result["step_id"] == "user"

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_elk(elk=mocked_elk):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device": elk_discovery_1.mac_address},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert not result["errors"]
    assert result2["step_id"] == "discovered_connection"
    with _patch_discovery(device=elk_discovery_1), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "protocol": "TLS 1.2",
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "ElkM1 ddeeff"
    assert result3["data"] == {
        "auto_configure": True,
        "host": "elksv1_2://127.0.0.1",
        "password": "test-password",
        "prefix": "",
        "username": "test-username",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    # Now try to add another instance with the different discovery info
    with _patch_discovery(device=elk_discovery_2):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert not result["errors"]
    assert result["step_id"] == "user"

    mocked_elk = mock_elk(invalid_auth=False, sync_complete=True)

    with _patch_elk(elk=mocked_elk):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device": elk_discovery_2.mac_address},
        )
        await hass.async_block_till_done()

    with _patch_discovery(device=elk_discovery_2), _patch_elk(elk=mocked_elk), patch(
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "protocol": "TLS 1.2",
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "ElkM1 ddeefe"
    assert result3["data"] == {
        "auto_configure": True,
        "host": "elksv1_2://127.0.0.2",
        "password": "test-password",
        "prefix": "ddeefe",
        "username": "test-username",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # Finally, try to add another instance manually with no discovery info

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
        "homeassistant.components.elkm1.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "protocol": "TLS 1.2",
                "address": "1.2.3.4",
                "prefix": "guest_house",
                "password": "test-password",
                "username": "test-username",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "guest_house"
    assert result2["data"] == {
        "auto_configure": True,
        "host": "elksv1_2://1.2.3.4",
        "prefix": "guest_house",
        "password": "test-password",
        "username": "test-username",
    }
    assert len(mock_setup_entry.mock_calls) == 1
