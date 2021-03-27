"""Test the System Bridge config flow."""
from unittest.mock import patch

from aiohttp.client_exceptions import ClientConnectionError
from systembridge.exceptions import BridgeAuthenticationException

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

FIXTURE_MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
FIXTURE_UUID = "e91bf575-56f3-4c83-8f42-70ac17adcd33"

FIXTURE_AUTH_INPUT = {CONF_API_KEY: "abc-123-def-456-ghi"}

FIXTURE_USER_INPUT = {
    CONF_API_KEY: "abc-123-def-456-ghi",
    CONF_HOST: "test-bridge",
    CONF_PORT: "9170",
}

FIXTURE_ZEROCONF_INPUT = {
    CONF_API_KEY: "abc-123-def-456-ghi",
    CONF_HOST: "1.1.1.1",
    CONF_PORT: "9170",
}

FIXTURE_ZEROCONF = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: 9170,
    "hostname": "test-bridge.local.",
    "type": "_system-bridge._udp.local.",
    "name": "System Bridge - test-bridge._system-bridge._udp.local.",
    "properties": {
        "address": "http://test-bridge:9170",
        "fqdn": "test-bridge",
        "host": "test-bridge",
        "ip": "1.1.1.1",
        "mac": FIXTURE_MAC_ADDRESS,
        "port": "9170",
        "uuid": FIXTURE_UUID,
    },
}


FIXTURE_OS = {
    "platform": "linux",
    "distro": "Ubuntu",
    "release": "20.10",
    "codename": "Groovy Gorilla",
    "kernel": "5.8.0-44-generic",
    "arch": "x64",
    "hostname": "test-bridge",
    "fqdn": "test-bridge.local",
    "codepage": "UTF-8",
    "logofile": "ubuntu",
    "serial": "abcdefghijklmnopqrstuvwxyz",
    "build": "",
    "servicepack": "",
    "uefi": True,
    "users": [],
}


FIXTURE_NETWORK = {
    "connections": [],
    "gatewayDefault": "192.168.1.1",
    "interfaceDefault": "wlp2s0",
    "interfaces": {
        "wlp2s0": {
            "iface": "wlp2s0",
            "ifaceName": "wlp2s0",
            "ip4": "1.1.1.1",
            "mac": FIXTURE_MAC_ADDRESS,
        },
    },
    "stats": {},
}

FIXTURE_SYSTEM = {
    "baseboard": {
        "manufacturer": "System manufacturer",
        "model": "Model",
        "version": "Rev X.0x",
        "serial": "1234567",
        "assetTag": "",
        "memMax": 134217728,
        "memSlots": 4,
    },
    "bios": {
        "vendor": "System vendor",
        "version": "12345",
        "releaseDate": "2019-11-13",
        "revision": "",
    },
    "chassis": {
        "manufacturer": "Default string",
        "model": "",
        "type": "Desktop",
        "version": "Default string",
        "serial": "Default string",
        "assetTag": "",
        "sku": "",
    },
    "system": {
        "manufacturer": "System manufacturer",
        "model": "System Product Name",
        "version": "System Version",
        "serial": "System Serial Number",
        "uuid": "abc123-def456",
        "sku": "SKU",
        "virtual": False,
    },
    "uuid": {
        "os": FIXTURE_UUID,
        "hardware": "abc123-def456",
        "macs": [FIXTURE_MAC_ADDRESS],
    },
}


FIXTURE_BASE_URL = (
    f"http://{FIXTURE_USER_INPUT[CONF_HOST]}:{FIXTURE_USER_INPUT[CONF_PORT]}"
)

FIXTURE_ZEROCONF_BASE_URL = (
    f"http://{FIXTURE_ZEROCONF[CONF_HOST]}:{FIXTURE_ZEROCONF[CONF_PORT]}"
)


async def test_user_flow(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
) -> None:
    """Test full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None

    aioclient_mock.get(f"{FIXTURE_BASE_URL}/os", json=FIXTURE_OS)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/network", json=FIXTURE_NETWORK)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/system", json=FIXTURE_SYSTEM)

    with patch(
        "homeassistant.components.system_bridge.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "test-bridge"
    assert result2["data"] == FIXTURE_USER_INPUT
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None

    aioclient_mock.get(f"{FIXTURE_BASE_URL}/os", exc=BridgeAuthenticationException)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/network", exc=BridgeAuthenticationException)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/system", exc=BridgeAuthenticationException)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None

    aioclient_mock.get(f"{FIXTURE_BASE_URL}/os", exc=ClientConnectionError)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/network", exc=ClientConnectionError)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/system", exc=ClientConnectionError)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_authorization_error(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
) -> None:
    """Test we show user form on authorization error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth"

    aioclient_mock.get(f"{FIXTURE_BASE_URL}/network", exc=BridgeAuthenticationException)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/os", exc=BridgeAuthenticationException)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/system", exc=BridgeAuthenticationException)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_AUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "reauth"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_connection_error(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
) -> None:
    """Test we show user form on connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth"

    aioclient_mock.get(f"{FIXTURE_BASE_URL}/os", exc=ClientConnectionError)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/network", exc=ClientConnectionError)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/system", exc=ClientConnectionError)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_AUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "reauth"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
) -> None:
    """Test reauth flow."""
    mock_config = MockConfigEntry(
        domain=DOMAIN, unique_id=FIXTURE_UUID, data=FIXTURE_USER_INPUT
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth"

    aioclient_mock.get(f"{FIXTURE_BASE_URL}/os", json=FIXTURE_OS)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/network", json=FIXTURE_NETWORK)
    aioclient_mock.get(f"{FIXTURE_BASE_URL}/system", json=FIXTURE_SYSTEM)

    with patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_successful"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_flow(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
) -> None:
    """Test zeroconf flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=FIXTURE_ZEROCONF,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None

    aioclient_mock.get(f"{FIXTURE_ZEROCONF_BASE_URL}/os", json=FIXTURE_OS)
    aioclient_mock.get(f"{FIXTURE_ZEROCONF_BASE_URL}/network", json=FIXTURE_NETWORK)
    aioclient_mock.get(f"{FIXTURE_ZEROCONF_BASE_URL}/system", json=FIXTURE_SYSTEM)

    with patch(
        "homeassistant.components.system_bridge.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "test-bridge"
    assert result2["data"] == FIXTURE_ZEROCONF_INPUT
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_cannot_connect(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
) -> None:
    """Test zeroconf cannot connect flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=FIXTURE_ZEROCONF,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None

    aioclient_mock.get(f"{FIXTURE_ZEROCONF_BASE_URL}/os", exc=ClientConnectionError)
    aioclient_mock.get(
        f"{FIXTURE_ZEROCONF_BASE_URL}/network", exc=ClientConnectionError
    )
    aioclient_mock.get(f"{FIXTURE_ZEROCONF_BASE_URL}/system", exc=ClientConnectionError)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_AUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "authenticate"
    assert result2["errors"] == {"base": "cannot_connect"}
