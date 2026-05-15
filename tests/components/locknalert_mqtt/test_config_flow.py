"""Tests for the LocknAlert MQTT config flow."""

from ipaddress import IPv4Address
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.locknalert_mqtt.config_flow import (
    PWD_NOT_CHANGED,
    extract_serial_from_discovery,
)
from homeassistant.components.locknalert_mqtt.const import (
    ATTR_TOPIC,
    CONF_BIRTH_MESSAGE,
    CONF_BRIDGE_SERIAL,
    CONF_BROKER,
    CONF_COMMAND_TOPIC,
    CONF_DISCOVERY_PREFIX,
    CONF_STATE_TOPIC,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DEFAULT_API_PORT,
    DEFAULT_DISCOVERY,
    DEFAULT_PREFIX,
    DISCOVERY_ATTR_API_PORT,
    DISCOVERY_ATTR_SERIAL,
    DOMAIN,
)
from homeassistant.const import CONF_DISCOVERY, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

MOCK_BRIDGE_HOST = "192.168.1.100"
MOCK_BRIDGE_SERIAL = "ABC123"
MOCK_BROKER = "192.168.1.100"
MOCK_PORT = 1883
MOCK_USERNAME = "mqtt_user"
MOCK_PASSWORD = "mqtt_pass"

MOCK_BOOTSTRAP_RESPONSE = {
    "host": MOCK_BROKER,
    "port": MOCK_PORT,
    "username": MOCK_USERNAME,
    "password": MOCK_PASSWORD,
}


def _make_zeroconf_info(
    serial: str = MOCK_BRIDGE_SERIAL,
    host: str = MOCK_BRIDGE_HOST,
    api_port: int | None = None,
) -> ZeroconfServiceInfo:
    """Build a ZeroconfServiceInfo for a LocknAlert bridge."""
    properties: dict = {}
    if api_port is not None:
        properties[DISCOVERY_ATTR_API_PORT] = str(api_port)
    return ZeroconfServiceInfo(
        ip_address=IPv4Address(host),
        ip_addresses=[IPv4Address(host)],
        port=443,
        hostname=f"{serial}.local.",
        type="_locknalert._tcp.local.",
        name=f"{serial}._locknalert._tcp.local.",
        properties=properties,
    )


# ---------------------------------------------------------------------------
# extract_serial_from_discovery
# ---------------------------------------------------------------------------


def test_extract_serial_from_name() -> None:
    """Serial is extracted from the discovery name prefix."""
    info = _make_zeroconf_info(serial="DEADBEEF")
    assert extract_serial_from_discovery(info) == "DEADBEEF"


def test_extract_serial_fallback_to_txt_property() -> None:
    """Serial falls back to TXT property when name has no prefix."""
    info = ZeroconfServiceInfo(
        ip_address=IPv4Address(MOCK_BRIDGE_HOST),
        ip_addresses=[IPv4Address(MOCK_BRIDGE_HOST)],
        port=443,
        hostname="bridge.local.",
        type="_locknalert._tcp.local.",
        name="",  # empty name so name-based extraction returns ""
        properties={DISCOVERY_ATTR_SERIAL: "TXT999"},
    )
    assert extract_serial_from_discovery(info) == "TXT999"


def test_extract_serial_returns_none_when_nothing_available() -> None:
    """Returns None when neither name nor TXT property has a serial."""
    info = ZeroconfServiceInfo(
        ip_address=IPv4Address(MOCK_BRIDGE_HOST),
        ip_addresses=[IPv4Address(MOCK_BRIDGE_HOST)],
        port=443,
        hostname="bridge.local.",
        type="_locknalert._tcp.local.",
        name="",
        properties={},
    )
    result = extract_serial_from_discovery(info)
    # name="" splits to [""], parts[0] == "" which is falsy — falls back to TXT → None
    assert result is None


# ---------------------------------------------------------------------------
# async_step_zeroconf
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bridge_api():
    """Return a patched LocknAlertBridgeApi that succeeds by default."""
    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.LocknAlertBridgeApi"
    ) as mock_cls:
        instance = MagicMock()
        instance.async_get_info = AsyncMock(return_value={"serial": MOCK_BRIDGE_SERIAL})
        instance.async_bootstrap = AsyncMock(return_value=MOCK_BOOTSTRAP_RESPONSE)
        mock_cls.return_value = instance
        yield mock_cls, instance


@pytest.fixture
def mock_try_connection_ok():
    """Patch try_connection to always succeed."""
    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.try_connection",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_client_session():
    """Patch aiohttp.ClientSession so no real network calls are made."""
    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.ClientSession"
    ) as mock_cls:
        session = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        yield session


async def test_zeroconf_happy_path(
    hass: HomeAssistant,
    mock_bridge_api: tuple,
    mock_client_session: AsyncMock,
    mock_try_connection_ok: MagicMock,
) -> None:
    """Zeroconf discovery → confirm → entry created."""
    _, api_instance = mock_bridge_api
    discovery_info = _make_zeroconf_info()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    with patch(
        "homeassistant.components.locknalert_mqtt.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_BRIDGE_SERIAL: MOCK_BRIDGE_SERIAL}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BROKER] == MOCK_BRIDGE_HOST
    assert result["data"][CONF_USERNAME] == MOCK_USERNAME
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD


async def test_zeroconf_aborts_when_no_serial(hass: HomeAssistant) -> None:
    """Zeroconf aborts when serial cannot be determined."""
    info = ZeroconfServiceInfo(
        ip_address=IPv4Address(MOCK_BRIDGE_HOST),
        ip_addresses=[IPv4Address(MOCK_BRIDGE_HOST)],
        port=443,
        hostname="bridge.local.",
        type="_locknalert._tcp.local.",
        name="",
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=info,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_determine_serial"


async def test_zeroconf_shows_form_when_bridge_unreachable(
    hass: HomeAssistant,
) -> None:
    """Zeroconf shows the confirm form even when bridge is unreachable.

    Connectivity is checked on submit, not on discovery, so the form always
    appears and the abort only happens after the user clicks Submit.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=_make_zeroconf_info(),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"


async def test_zeroconf_confirm_aborts_on_cannot_connect(hass: HomeAssistant) -> None:
    """Confirm step aborts when bridge is not reachable on submit."""
    from aiolocknalert import LocknAlertCannotConnect  # noqa: PLC0415

    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.LocknAlertBridgeApi"
    ) as mock_cls:
        instance = MagicMock()
        instance.async_get_info = AsyncMock(side_effect=LocknAlertCannotConnect)
        instance.async_bootstrap = AsyncMock(side_effect=LocknAlertCannotConnect)
        mock_cls.return_value = instance
        with patch(
            "homeassistant.components.locknalert_mqtt.config_flow.ClientSession"
        ) as cs:
            session = AsyncMock()
            cs.return_value.__aenter__ = AsyncMock(return_value=session)
            cs.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "zeroconf"},
                data=_make_zeroconf_info(),
            )
            assert result["type"] == FlowResultType.FORM

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_BRIDGE_SERIAL: MOCK_BRIDGE_SERIAL}
            )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_confirm_aborts_on_invalid_response(
    hass: HomeAssistant,
) -> None:
    """Confirm step aborts when bridge returns an unexpected response on submit."""
    from aiolocknalert import LocknAlertInvalidResponse

    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.LocknAlertBridgeApi"
    ) as mock_cls:
        instance = MagicMock()
        instance.async_get_info = AsyncMock(side_effect=LocknAlertInvalidResponse)
        instance.async_bootstrap = AsyncMock(side_effect=LocknAlertInvalidResponse)
        mock_cls.return_value = instance
        with patch(
            "homeassistant.components.locknalert_mqtt.config_flow.ClientSession"
        ) as cs:
            session = AsyncMock()
            cs.return_value.__aenter__ = AsyncMock(return_value=session)
            cs.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "zeroconf"},
                data=_make_zeroconf_info(),
            )
            assert result["type"] == FlowResultType.FORM

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_BRIDGE_SERIAL: MOCK_BRIDGE_SERIAL}
            )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "invalid_response"


async def test_zeroconf_aborts_on_duplicate(hass: HomeAssistant) -> None:
    """Zeroconf aborts when an entry for that serial already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={CONF_BROKER: MOCK_BROKER},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=_make_zeroconf_info(),
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] in ("already_configured", "single_instance_allowed")


async def test_zeroconf_uses_custom_api_port(
    hass: HomeAssistant,
    mock_bridge_api: tuple,
    mock_client_session: AsyncMock,
    mock_try_connection_ok: MagicMock,
) -> None:
    """Bridge API is called with the port from TXT properties."""
    mock_cls, _ = mock_bridge_api
    discovery_info = _make_zeroconf_info(api_port=8443)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.FORM

    mock_cls.assert_called_once_with(host=MOCK_BRIDGE_HOST, port=8443, verify_ssl=False)


async def test_zeroconf_uses_default_api_port_when_missing(
    hass: HomeAssistant,
    mock_bridge_api: tuple,
    mock_client_session: AsyncMock,
    mock_try_connection_ok: MagicMock,
) -> None:
    """DEFAULT_API_PORT is used when TXT properties don't include api_port."""
    mock_cls, _ = mock_bridge_api
    discovery_info = _make_zeroconf_info()  # no api_port in properties

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info,
    )
    mock_cls.assert_called_once_with(
        host=MOCK_BRIDGE_HOST, port=DEFAULT_API_PORT, verify_ssl=False
    )


# ---------------------------------------------------------------------------
# async_step_zeroconf_confirm
# ---------------------------------------------------------------------------


async def test_zeroconf_confirm_shows_form_then_bootstraps(
    hass: HomeAssistant,
    mock_bridge_api: tuple,
    mock_client_session: AsyncMock,
    mock_try_connection_ok: MagicMock,
) -> None:
    """Confirm form shows current serial; submitting triggers bootstrap."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=_make_zeroconf_info(),
    )
    assert result["step_id"] == "zeroconf_confirm"

    with patch(
        "homeassistant.components.locknalert_mqtt.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_BRIDGE_SERIAL: MOCK_BRIDGE_SERIAL}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_zeroconf_confirm_serial_override(
    hass: HomeAssistant,
    mock_bridge_api: tuple,
    mock_client_session: AsyncMock,
    mock_try_connection_ok: MagicMock,
) -> None:
    """User can override the serial during confirm."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=_make_zeroconf_info(),
    )
    with patch(
        "homeassistant.components.locknalert_mqtt.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_BRIDGE_SERIAL: "OVERRIDE99"},
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BRIDGE_SERIAL] == "OVERRIDE99"


# ---------------------------------------------------------------------------
# _async_bootstrap_from_bridge failures
# ---------------------------------------------------------------------------


async def test_bootstrap_aborts_on_cannot_connect(
    hass: HomeAssistant,
    mock_client_session: AsyncMock,
) -> None:
    """Bootstrap step aborts when bridge MQTT bootstrap fails."""
    from aiolocknalert import LocknAlertCannotConnect

    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.LocknAlertBridgeApi"
    ) as mock_cls:
        instance = MagicMock()
        instance.async_get_info = AsyncMock(return_value={})
        instance.async_bootstrap = AsyncMock(side_effect=LocknAlertCannotConnect)
        mock_cls.return_value = instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=_make_zeroconf_info(),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_BRIDGE_SERIAL: MOCK_BRIDGE_SERIAL}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_bootstrap_aborts_on_invalid_response(
    hass: HomeAssistant,
    mock_client_session: AsyncMock,
) -> None:
    """Bootstrap step aborts when bridge returns an unexpected response."""
    from aiolocknalert import LocknAlertInvalidResponse

    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.LocknAlertBridgeApi"
    ) as mock_cls:
        instance = MagicMock()
        instance.async_get_info = AsyncMock(return_value={})
        instance.async_bootstrap = AsyncMock(side_effect=LocknAlertInvalidResponse)
        mock_cls.return_value = instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=_make_zeroconf_info(),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_BRIDGE_SERIAL: MOCK_BRIDGE_SERIAL}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "invalid_response"


async def test_bootstrap_aborts_when_mqtt_cannot_connect(
    hass: HomeAssistant,
    mock_bridge_api: tuple,
    mock_client_session: AsyncMock,
) -> None:
    """Bootstrap succeeds but MQTT broker is unreachable."""
    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.try_connection",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=_make_zeroconf_info(),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_BRIDGE_SERIAL: MOCK_BRIDGE_SERIAL}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect_mqtt"


# ---------------------------------------------------------------------------
# async_step_broker (manual setup)
# ---------------------------------------------------------------------------


async def test_broker_step_shows_form(hass: HomeAssistant) -> None:
    """Manual broker step shows a form asking for broker address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "broker"


async def test_broker_step_creates_entry(
    hass: HomeAssistant,
    mock_bridge_api: tuple,
    mock_client_session: AsyncMock,
    mock_try_connection_ok: MagicMock,
) -> None:
    """Valid broker input with successful bridge bootstrap creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch(
        "homeassistant.components.locknalert_mqtt.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_BROKER: MOCK_BROKER},
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BROKER] == MOCK_BROKER


async def test_broker_step_shows_error_on_cannot_connect(
    hass: HomeAssistant,
    mock_client_session: AsyncMock,
) -> None:
    """Bridge API error on manual broker setup shows an error on the form."""
    from aiolocknalert import LocknAlertCannotConnect

    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.LocknAlertBridgeApi"
    ) as mock_cls:
        instance = MagicMock()
        instance.async_get_info = AsyncMock(side_effect=LocknAlertCannotConnect)
        instance.async_bootstrap = AsyncMock(side_effect=LocknAlertCannotConnect)
        mock_cls.return_value = instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_BROKER: MOCK_BROKER},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


# ---------------------------------------------------------------------------
# async_step_reauth
# ---------------------------------------------------------------------------


async def test_reauth_shows_form(hass: HomeAssistant) -> None:
    """Reauth step shows a form with username/password fields."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={
            CONF_BROKER: MOCK_BROKER,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_updates_entry_on_valid_credentials(hass: HomeAssistant) -> None:
    """Reauth with valid credentials updates the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={
            CONF_BROKER: MOCK_BROKER,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: "old_pass",
        },
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )

    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.try_connection",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: "new_pass"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new_pass"


async def test_reauth_shows_error_on_invalid_credentials(
    hass: HomeAssistant,
) -> None:
    """Reauth with invalid credentials shows an error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={
            CONF_BROKER: MOCK_BROKER,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )

    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.try_connection",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: "wrong"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_reauth_pwd_not_changed_sentinel_keeps_existing_password(
    hass: HomeAssistant,
) -> None:
    """Submitting PWD_NOT_CHANGED sentinel preserves the existing password."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={
            CONF_BROKER: MOCK_BROKER,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: "original_pass",
        },
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )

    with patch(
        "homeassistant.components.locknalert_mqtt.config_flow.try_connection",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: PWD_NOT_CHANGED},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "original_pass"


# ---------------------------------------------------------------------------
# async_step_reconfigure
# ---------------------------------------------------------------------------


async def test_reconfigure_shows_broker_form(hass: HomeAssistant) -> None:
    """Reconfigure step delegates to the broker form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={CONF_BROKER: MOCK_BROKER},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "broker"


async def test_reconfigure_updates_entry(
    hass: HomeAssistant,
    mock_bridge_api: tuple,
    mock_client_session: AsyncMock,
    mock_try_connection_ok: MagicMock,
) -> None:
    """Reconfigure with valid input updates the config entry and aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={CONF_BROKER: "old-broker"},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_BROKER: MOCK_BROKER},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_BROKER] == MOCK_BROKER


# ---------------------------------------------------------------------------
# Edge-case: malformed api_port TXT record
# ---------------------------------------------------------------------------


async def test_zeroconf_malformed_api_port_uses_default(
    hass: HomeAssistant,
    mock_bridge_api: tuple,
    mock_client_session: AsyncMock,
    mock_try_connection_ok: MagicMock,
) -> None:
    """Invalid api_port TXT value falls back to DEFAULT_API_PORT."""
    mock_cls, _ = mock_bridge_api
    # Inject a non-integer api_port value into TXT properties
    info = ZeroconfServiceInfo(
        ip_address=IPv4Address(MOCK_BRIDGE_HOST),
        ip_addresses=[IPv4Address(MOCK_BRIDGE_HOST)],
        port=443,
        hostname=f"{MOCK_BRIDGE_SERIAL}.local.",
        type="_locknalert._tcp.local.",
        name=f"{MOCK_BRIDGE_SERIAL}._locknalert._tcp.local.",
        properties={DISCOVERY_ATTR_API_PORT: "not-a-number"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=info,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    mock_cls.assert_called_once_with(
        host=MOCK_BRIDGE_HOST, port=DEFAULT_API_PORT, verify_ssl=False
    )


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


async def test_options_flow_shows_form(
    hass: HomeAssistant,
) -> None:
    """Options flow shows a form on first open."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={CONF_BROKER: MOCK_BROKER},
        options={},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "options"


async def test_options_flow_saves_discovery_toggle(
    hass: HomeAssistant,
) -> None:
    """Toggling discovery off saves correctly to options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={CONF_BROKER: MOCK_BROKER},
        options={},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DISCOVERY: False,
            CONF_DISCOVERY_PREFIX: DEFAULT_PREFIX,
            "birth_enable": False,
            "will_enable": False,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DISCOVERY] is False


async def test_options_flow_invalid_discovery_prefix_shows_error(
    hass: HomeAssistant,
) -> None:
    """Invalid discovery prefix shows a validation error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={CONF_BROKER: MOCK_BROKER},
        options={},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DISCOVERY: DEFAULT_DISCOVERY,
            CONF_DISCOVERY_PREFIX: "#invalid/prefix",
            "birth_enable": False,
            "will_enable": False,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "bad_discovery_prefix"


async def test_options_flow_saves_birth_message(
    hass: HomeAssistant,
) -> None:
    """Birth message is saved when birth_enable is True."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={CONF_BROKER: MOCK_BROKER},
        options={},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DISCOVERY: DEFAULT_DISCOVERY,
            CONF_DISCOVERY_PREFIX: DEFAULT_PREFIX,
            "birth_enable": True,
            "birth_topic": "homeassistant/status",
            "birth_payload": "online",
            "birth_qos": 0,
            "birth_retain": False,
            "will_enable": False,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert CONF_BIRTH_MESSAGE in result["data"]
    assert result["data"][CONF_BIRTH_MESSAGE][ATTR_TOPIC] == "homeassistant/status"


# ---------------------------------------------------------------------------
# Subentry flow (MQTT device wizard — alarm_control_panel)
# ---------------------------------------------------------------------------


async def test_subentry_flow_shows_device_form_on_init(
    hass: HomeAssistant,
) -> None:
    """Starting a subentry flow shows the device form first."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={CONF_BROKER: MOCK_BROKER},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": "user"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "device"


async def test_subentry_flow_creates_alarm_control_panel(
    hass: HomeAssistant,
) -> None:
    """Full subentry wizard creates an alarm_control_panel subentry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_BRIDGE_SERIAL,
        data={CONF_BROKER: MOCK_BROKER},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    # Step 1 — start wizard, device name
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": "user"},
    )
    assert result["step_id"] == "device"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Test Alarm Panel"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "entity"

    # Step 2 — choose entity platform
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"platform": "alarm_control_panel"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "entity_platform_config"

    # Step 3 — alarm_control_panel platform settings
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "supported_features": ["arm_home", "arm_away"],
            "alarm_control_panel_code_mode": "local_code",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "mqtt_platform_config"

    # Step 4 — MQTT topics
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_COMMAND_TOPIC: "alarm/set",
            CONF_STATE_TOPIC: "alarm/state",
            "code": "1234",
            "code_arm_required": True,
            "code_disarm_required": True,
            "code_trigger_required": True,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
