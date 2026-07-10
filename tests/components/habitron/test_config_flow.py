"""Tests for the Habitron config flow."""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import HabitronError, HabitronTimeoutError
import pytest

from homeassistant import config_entries
from homeassistant.components.habitron.config_flow import (
    KEY_HOST,
    CannotConnect,
    ConfigFlow,
    HostNotFound,
    InvalidHost,
    validate_input,
)
from homeassistant.components.habitron.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import MOCK_CONFIG_DATA, MOCK_HOST, MOCK_NAME, MOCK_SERIAL, MOCK_UDN

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """The manual user flow creates an entry when the hub responds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"] == MOCK_CONFIG_DATA


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A failing connect probe surfaces ``cannot_connect``."""
    mock_habitron_client.return_value = (False, "")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An identical config aborts with ``already_configured``.

    The user step falls back to ``habitron_{host}`` for the unique id
    when no discovery response arrives, so we register an existing
    entry with that same id to trigger the abort path.
    """
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=f"habitron_{MOCK_HOST}",
        data=MOCK_CONFIG_DATA,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_discovery_with_udn(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """SSDP discovery prefers the UDN as unique id."""
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    # Confirm step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == MOCK_UDN


async def test_ssdp_discovery_serial_fallback(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """When no UDN, the UPnP serialNumber is used."""
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_SERIAL: MOCK_SERIAL},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == MOCK_SERIAL


async def test_ssdp_legacy_unique_id_migrated(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A pre-existing host-based entry gets migrated on rediscovery."""
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=f"habitron_{MOCK_HOST}",
        data=MOCK_CONFIG_DATA,
    )
    legacy_entry.add_to_hass(hass)

    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    # Old host-based entry should already have been rewritten and the
    # flow aborted as "already configured" against the new id.
    await hass.async_block_till_done()
    assert legacy_entry.unique_id == MOCK_UDN
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_no_host(
    hass: HomeAssistant,
    setup_homeassistant: None,
) -> None:
    """SSDP without a hostname is aborted."""
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=None,
        upnp={},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_host_in_ssdp"


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (HabitronTimeoutError("timeout"), "cannot_connect"),
        (ConnectionRefusedError("refused"), "cannot_connect"),
    ],
)
async def test_user_flow_exception_mapping(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    exception: Exception,
    expected: str,
) -> None:
    """Connection errors map to expected form errors."""
    mock_habitron_client.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


# ---------- unit tests for the helper layer ----------


async def test_validate_input_local_loopback_rewrites_host(
    hass: HomeAssistant,
    mock_habitron_client: MagicMock,
) -> None:
    """A host equal to one of our own IPs is rewritten to ``local``."""

    data = {KEY_HOST: "192.168.1.10", "websock_token": ""}
    info = await validate_input(hass, data)
    assert data[KEY_HOST] == "local"
    assert info == {"title": MOCK_NAME}


async def test_validate_input_invalid_host_too_short(hass: HomeAssistant) -> None:
    """A host string shorter than 4 chars raises ``InvalidHost``."""

    with (
        patch(
            "homeassistant.components.habitron.config_flow.network.async_get_source_ip",
            new=AsyncMock(return_value="10.0.0.5"),
        ),
        pytest.raises(InvalidHost),
    ):
        await validate_input(
            hass,
            {KEY_HOST: "abc", "websock_token": ""},
        )


async def test_validate_input_host_not_found_for_dns_failure(
    hass: HomeAssistant,
) -> None:
    """A socket.gaierror surfaces as ``HostNotFound``."""

    with (
        patch(
            "homeassistant.components.habitron.config_flow.network.async_get_source_ip",
            new=AsyncMock(return_value="10.0.0.5"),
        ),
        patch(
            "homeassistant.components.habitron.config_flow.test_connection",
            side_effect=socket.gaierror("dns fail"),
        ),
        pytest.raises(HostNotFound),
    ):
        await validate_input(
            hass,
            {KEY_HOST: MOCK_HOST, "websock_token": ""},
        )


# ---------- ConfigFlow._is_device_already_configured ----------


async def test_is_device_already_configured_host_match(hass: HomeAssistant) -> None:
    """A pre-existing entry whose host matches reports as configured."""

    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="existing-id",
        data={"habitron_host": MOCK_HOST},
    ).add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    assert flow._is_device_already_configured(MOCK_HOST) is True
    assert flow._is_device_already_configured("other-host") is False


async def test_is_device_already_configured_ip_match(hass: HomeAssistant) -> None:
    """A pre-existing entry whose host equals the IP reports as configured."""

    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="existing-id",
        data={"habitron_host": "10.0.0.1"},
    ).add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    assert flow._is_device_already_configured("hub-x", ip="10.0.0.1") is True


# ---------- SSDP with no UDN + discovery fallback ----------


async def test_ssdp_discovery_falls_back_to_discovery_serial(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """A discovery without UDN/serial picks the serial from the network probe."""
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={},
    )

    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[{"ip": MOCK_HOST, "serial": "UDP-SER-1"}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery,
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == "UDP-SER-1"


async def test_ssdp_discovery_no_udn_no_probe_falls_back_to_host_id(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """Without UDN, serial or matching probe device, the host string is used."""
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={},
    )

    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery,
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == f"habitron_{MOCK_HOST}"


async def test_ssdp_discovery_confirm_handles_validate_error(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A confirm step that fails validation with an unexpected error aborts."""
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=ValueError("totally unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_ssdp_discovery_confirm_cannot_connect_retries(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A briefly-offline discovered hub re-shows the confirm form to retry."""
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["errors"] == {"base": "cannot_connect"}


# ---------- user flow exception mapping ----------


async def test_user_flow_host_not_found_via_validate_input(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A HostNotFound raised from validate_input maps to ``host_not_found``."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=HostNotFound("dns"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_DATA
        )
    assert result["errors"] == {"base": "host_not_found"}


async def test_user_flow_truly_unknown_exception_maps_to_unknown(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An exception type the user step does not know surfaces as ``unknown``."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=ValueError("totally unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_DATA
        )
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_short_host_maps_to_host_not_found(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A host string shorter than 4 chars triggers ``host_not_found``."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**MOCK_CONFIG_DATA, "habitron_host": "ab"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "host_not_found"}


async def test_user_flow_unexpected_exception_maps_to_unknown(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An unexpected error from the probe propagates and surfaces as ``unknown``."""
    mock_habitron_client.side_effect = RuntimeError("boom")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


# ---------- user step pre-fill from discovery ----------


async def test_user_step_prefills_host_from_discovery(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """The user step pre-fills the host field from a discovered device."""
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[{"ip": "10.0.0.99", "serial": "s"}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # The form's data-schema default should now reflect the discovered ip.
    schema = result["data_schema"].schema
    # Find the KEY_HOST default by walking the schema vol.Required keys.
    default = None
    for key in schema:
        if getattr(key, "schema", None) == "habitron_host":
            default = key.default()
            break
    assert default == "10.0.0.99"


async def test_user_step_survives_discovery_failure(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A discovery error is swallowed so the manual host form is still shown."""
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(side_effect=HabitronError("scan blew up")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_flow_own_ip_canonicalizes_unique_id(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """An own-IP host is canonicalized to ``local`` before deriving the id.

    ``validate_input`` rewrites an own IP to the ``local`` sentinel, so the
    fallback unique_id must be built from the canonical host to stay consistent.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # 192.168.1.10 is the (mocked) own source IP.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"habitron_host": "192.168.1.10", "websock_token": ""},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["habitron_host"] == "local"
    assert result["result"].unique_id == "habitron_local"


async def test_user_flow_picks_up_serial_from_discovery_probe(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """A matching discovery serial becomes the unique id."""
    with patch(
        "homeassistant.components.habitron.config_flow.discover_smarthubs",
        new=AsyncMock(return_value=[{"ip": MOCK_HOST, "serial": "SERIAL-X"}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_DATA
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "SERIAL-X"
