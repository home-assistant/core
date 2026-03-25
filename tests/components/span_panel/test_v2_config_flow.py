"""Tests for v2 eBus config flow changes."""

from __future__ import annotations

import ipaddress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from span_panel_api import DetectionResult, V2AuthResponse, V2StatusInfo
from span_panel_api.exceptions import SpanPanelAuthError, SpanPanelConnectionError

from homeassistant import config_entries
from homeassistant.components.span_panel import (
    CURRENT_CONFIG_VERSION,
    async_migrate_entry,
    async_setup_entry,
)
from homeassistant.components.span_panel.config_flow import (
    SpanPanelConfigFlow,
    TriggerFlowType,
)
from homeassistant.components.span_panel.const import (
    CONF_API_VERSION,
    CONF_EBUS_BROKER_HOST,
    CONF_EBUS_BROKER_PASSWORD,
    CONF_EBUS_BROKER_PORT,
    CONF_EBUS_BROKER_USERNAME,
    CONF_HOP_PASSPHRASE,
    CONF_HTTP_PORT,
    CONF_PANEL_SERIAL,
    CONF_REGISTERED_FQDN,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

# Shared mock detection for a different panel (used in reconfigure/duplicate tests)
MOCK_V2_DETECTION_OTHER = DetectionResult(
    api_version="v2",
    status_info=V2StatusInfo(
        serial_number="SPAN-V2-OTHER",
        firmware_version="2.0.0",
    ),
)

# ---------- helpers ----------

MOCK_HOST = "192.168.1.100"
MOCK_PASSPHRASE = "correct-horse-battery-staple"

MOCK_V2_DETECTION = DetectionResult(
    api_version="v2",
    status_info=V2StatusInfo(
        serial_number="SPAN-V2-001",
        firmware_version="2.0.0",
    ),
)

MOCK_V2_DETECTION_PROXIMITY_PROVEN = DetectionResult(
    api_version="v2",
    status_info=V2StatusInfo(
        serial_number="SPAN-V2-001",
        firmware_version="2.0.0",
        proximity_proven=True,
    ),
)

MOCK_V2_DETECTION_PROXIMITY_NOT_PROVEN = DetectionResult(
    api_version="v2",
    status_info=V2StatusInfo(
        serial_number="SPAN-V2-001",
        firmware_version="2.0.0",
        proximity_proven=False,
    ),
)

MOCK_V1_DETECTION = DetectionResult(
    api_version="v1",
    status_info=None,
)

MOCK_V2_AUTH = V2AuthResponse(
    access_token="v2-token-abc",
    token_type="bearer",
    iat_ms=1700000000000,
    ebus_broker_host="192.168.1.100",
    ebus_broker_mqtts_port=8883,
    ebus_broker_ws_port=8080,
    ebus_broker_wss_port=8443,
    ebus_broker_username="span-user",
    ebus_broker_password="mqtt-secret",
    hostname="span-panel.local",
    serial_number="SPAN-V2-001",
    hop_passphrase=MOCK_PASSPHRASE,
)


# ---------- v2 detection routing ----------


@pytest.mark.asyncio
async def test_user_flow_detects_v2_and_shows_auth_choice(hass: HomeAssistant) -> None:
    """When detect_api_version returns v2, the user flow should show the auth choice menu."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

        assert result2["type"] == FlowResultType.MENU
        assert result2["step_id"] == "choose_v2_auth"
        assert "auth_passphrase" in result2["menu_options"]
        assert "auth_proximity" in result2["menu_options"]


@pytest.mark.asyncio
async def test_user_flow_passes_ha_httpx_client_to_detect_api_version(
    hass: HomeAssistant,
) -> None:
    """User flow should pass the Home Assistant shared httpx client to detection."""
    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.get_async_client",
            return_value=fake_client,
        ) as mock_get_client,
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ) as mock_detect,
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    mock_get_client.assert_called_once_with(hass, verify_ssl=False)
    mock_detect.assert_awaited_once_with(MOCK_HOST, port=80, httpx_client=fake_client)


@pytest.mark.asyncio
async def test_user_flow_v1_aborts(hass: HomeAssistant) -> None:
    """When detect_api_version returns v1, the user flow should abort (v1 not supported)."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V1_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

        # Non-v2 panels are not supported and should abort
        assert result2["type"] in (FlowResultType.FORM, FlowResultType.ABORT)


# ---------- passphrase auth ----------


@pytest.mark.asyncio
async def test_passphrase_auth_success(hass: HomeAssistant) -> None:
    """Successful passphrase auth should proceed to naming step."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_passphrase",
            return_value=MOCK_V2_AUTH,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        assert result2["step_id"] == "choose_v2_auth"

        # Select passphrase auth from the menu
        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )
        assert result2b["step_id"] == "auth_passphrase"

        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {CONF_HOP_PASSPHRASE: MOCK_PASSPHRASE},
        )

        assert result3["type"] == FlowResultType.FORM
        assert result3["step_id"] == "choose_entity_naming_initial"


@pytest.mark.asyncio
async def test_passphrase_auth_bad_passphrase(hass: HomeAssistant) -> None:
    """Bad passphrase should re-show the form with invalid_auth error."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_passphrase",
            side_effect=SpanPanelAuthError("Invalid passphrase"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

        # Select passphrase auth from the menu
        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {CONF_HOP_PASSPHRASE: "wrong-passphrase"},
        )

        assert result3["type"] == FlowResultType.FORM
        assert result3["step_id"] == "auth_passphrase"
        assert result3["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_passphrase_auth_connection_error(hass: HomeAssistant) -> None:
    """Connection error should re-show form with cannot_connect."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_passphrase",
            side_effect=SpanPanelConnectionError("timeout"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

        # Select passphrase auth from the menu
        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {CONF_HOP_PASSPHRASE: MOCK_PASSPHRASE},
        )

        assert result3["type"] == FlowResultType.FORM
        assert result3["step_id"] == "auth_passphrase"
        assert result3["errors"] == {"base": "cannot_connect"}


# ---------- v2 entry creation ----------


@pytest.mark.usefixtures("socket_enabled")
@pytest.mark.asyncio
async def test_v2_entry_contains_mqtt_credentials(hass: HomeAssistant) -> None:
    """A completed v2 flow should create an entry with MQTT broker fields."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_passphrase",
            return_value=MOCK_V2_AUTH,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Step 1: submit host
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

        # Step 2: choose auth method (passphrase)
        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )

        # Step 3: submit passphrase
        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {CONF_HOP_PASSPHRASE: MOCK_PASSPHRASE},
        )

        # Step 4: choose entity naming pattern (accept default)
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {"entity_naming_pattern": "friendly_names"},
        )

        assert result4["type"] == FlowResultType.CREATE_ENTRY
        data = result4["data"]
        assert data[CONF_API_VERSION] == "v2"
        assert data[CONF_HOST] == MOCK_HOST
        assert data[CONF_ACCESS_TOKEN] == "v2-token-abc"
        assert data[CONF_EBUS_BROKER_HOST] == "192.168.1.100"
        assert data[CONF_EBUS_BROKER_PORT] == 8883
        assert data[CONF_EBUS_BROKER_USERNAME] == "span-user"
        assert data[CONF_EBUS_BROKER_PASSWORD] == "mqtt-secret"
        assert data[CONF_HOP_PASSPHRASE] == MOCK_PASSPHRASE
        assert data[CONF_PANEL_SERIAL] == "SPAN-V2-001"


# ---------- config entry migration (2.0.4 baseline) ----------


@pytest.mark.asyncio
async def test_config_flow_uses_current_config_entry_version() -> None:
    """New core entries should use the current storage version."""

    assert SpanPanelConfigFlow.VERSION == CURRENT_CONFIG_VERSION


@pytest.mark.asyncio
async def test_migration_updates_older_entry_to_current_version(
    hass: HomeAssistant,
) -> None:
    """Core should treat older entries as already storage-compatible."""
    entry = MockConfigEntry(
        version=2,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: "192.168.1.50",
            CONF_ACCESS_TOKEN: "old-token",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SN-LIVE-001",
    )
    entry.add_to_hass(hass)

    result = await async_migrate_entry(hass, entry)

    assert result is True
    assert entry.version == 6
    assert CONF_API_VERSION not in entry.data


@pytest.mark.asyncio
async def test_simulation_entry_is_skipped_during_setup(hass: HomeAssistant) -> None:
    """Simulation entries are not set up in core."""
    entry = MockConfigEntry(
        version=5,
        minor_version=1,
        domain=DOMAIN,
        title="Span Simulator",
        data={
            CONF_HOST: "sim-001",
            CONF_ACCESS_TOKEN: "simulator_token",
            CONF_API_VERSION: "simulation",
            "simulation_mode": True,
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SIM-001",
    )
    entry.add_to_hass(hass)

    # Setup is skipped for simulation entries
    setup_result = await async_setup_entry(hass, entry)
    assert setup_result is False


# ---------- zeroconf v2 discovery ----------


@pytest.mark.asyncio
async def test_zeroconf_ebus_discovery_routes_to_confirm(hass: HomeAssistant) -> None:
    """Discovering an _ebus._tcp.local. service should set api_version=v2 and show confirm."""

    discovery_info = ZeroconfServiceInfo(
        ip_address=ipaddress.IPv4Address("192.168.1.200"),
        ip_addresses=[ipaddress.IPv4Address("192.168.1.200")],
        hostname="span-panel.local.",
        name="SPAN Panel._ebus._tcp.local.",
        port=8883,
        properties={},
        type="_ebus._tcp.local.",
    )

    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.is_ipv4_address",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm_discovery"


# ---------- reauth ----------


@pytest.mark.asyncio
async def test_reauth_v2_shows_auth_choice(hass: HomeAssistant) -> None:
    """Reauth for a v2 panel should show the auth choice menu."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "old-v2-token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.span_panel.config_flow.detect_api_version",
        return_value=MOCK_V2_DETECTION,
    ):
        result = await entry.start_reauth_flow(hass)

        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "choose_v2_auth"


@pytest.mark.asyncio
async def test_reauth_aborts_cannot_connect_when_probe_failed(
    hass: HomeAssistant,
) -> None:
    """Reauth must abort with cannot_connect when detection probe fails."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "old-v2-token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    probe_failed = DetectionResult(
        api_version="v1",
        status_info=None,
        probe_failed=True,
    )
    with patch(
        "homeassistant.components.span_panel.config_flow.detect_api_version",
        return_value=probe_failed,
    ):
        result = await entry.start_reauth_flow(hass)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.asyncio
async def test_reauth_v2_success_updates_entry(hass: HomeAssistant) -> None:
    """Successful v2 reauth should update the config entry with new MQTT creds."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "old-v2-token",
            CONF_API_VERSION: "v2",
            CONF_EBUS_BROKER_HOST: "old-host",
            CONF_EBUS_BROKER_PORT: 8883,
            CONF_EBUS_BROKER_USERNAME: "old-user",
            CONF_EBUS_BROKER_PASSWORD: "old-pass",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_passphrase",
            return_value=MOCK_V2_AUTH,
        ),
        patch.object(hass.config_entries, "async_reload", return_value=True),
    ):
        result = await entry.start_reauth_flow(hass)
        assert result["step_id"] == "choose_v2_auth"

        # Select passphrase auth from the menu
        result1b = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )
        assert result1b["step_id"] == "auth_passphrase"

        result2 = await hass.config_entries.flow.async_configure(
            result1b["flow_id"],
            {CONF_HOP_PASSPHRASE: MOCK_PASSPHRASE},
        )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"

    assert entry.data[CONF_ACCESS_TOKEN] == "v2-token-abc"
    assert entry.data[CONF_EBUS_BROKER_USERNAME] == "span-user"
    assert entry.data[CONF_EBUS_BROKER_PASSWORD] == "mqtt-secret"


# ---------- user flow error paths ----------


@pytest.mark.asyncio
async def test_user_flow_empty_host(hass: HomeAssistant) -> None:
    """Submitting an empty host should re-show the form with host_required error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: ""},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "host_required"}


@pytest.mark.asyncio
async def test_user_flow_host_unreachable(hass: HomeAssistant) -> None:
    """Unreachable host should re-show the form with cannot_connect error."""
    with patch(
        "homeassistant.components.span_panel.config_flow.validate_host",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "10.0.0.99"},
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "user"
        assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_user_flow_cannot_connect_when_second_detection_probe_failed(
    hass: HomeAssistant,
) -> None:
    """Second detection with probe_failed must show cannot_connect, not v1_not_supported."""
    probe_failed = DetectionResult(
        api_version="v1",
        status_info=None,
        probe_failed=True,
    )
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=probe_failed,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_user_flow_recovery_after_bad_host(hass: HomeAssistant) -> None:
    """User can complete setup after an initial host validation failure."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            side_effect=[False, True],
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # First attempt fails
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "bad-host"},
        )
        assert result2["errors"] == {"base": "cannot_connect"}

        # Second attempt succeeds
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        assert result3["type"] == FlowResultType.MENU
        assert result3["step_id"] == "choose_v2_auth"


# ---------- passphrase auth: empty passphrase ----------


@pytest.mark.asyncio
async def test_passphrase_auth_empty_passphrase(hass: HomeAssistant) -> None:
    """Empty passphrase should re-show the form with invalid_auth error."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {CONF_HOP_PASSPHRASE: ""},
        )

        assert result3["type"] == FlowResultType.FORM
        assert result3["step_id"] == "auth_passphrase"
        assert result3["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_passphrase_auth_recovery_after_error(hass: HomeAssistant) -> None:
    """User can complete auth after an initial bad passphrase."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_passphrase",
            side_effect=[SpanPanelAuthError("bad"), MOCK_V2_AUTH],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )

        # First attempt: bad passphrase
        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {CONF_HOP_PASSPHRASE: "wrong"},
        )
        assert result3["errors"] == {"base": "invalid_auth"}

        # Second attempt: correct passphrase
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {CONF_HOP_PASSPHRASE: MOCK_PASSPHRASE},
        )
        assert result4["type"] == FlowResultType.FORM
        assert result4["step_id"] == "choose_entity_naming_initial"


# ---------- proximity auth ----------


@pytest.mark.asyncio
async def test_proximity_auth_success(hass: HomeAssistant) -> None:
    """Successful proximity auth should proceed to naming step."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            side_effect=[MOCK_V2_DETECTION, MOCK_V2_DETECTION_PROXIMITY_PROVEN],
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_proximity",
            return_value=MOCK_V2_AUTH,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        assert result2["step_id"] == "choose_v2_auth"

        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_proximity"},
        )
        assert result2b["step_id"] == "auth_proximity"

        # User confirms they opened the door
        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {"next_step_id": "auth_proximity_confirm"},
        )

        assert result3["type"] == FlowResultType.FORM
        assert result3["step_id"] == "choose_entity_naming_initial"


@pytest.mark.asyncio
async def test_proximity_not_proven_returns_to_menu(hass: HomeAssistant) -> None:
    """Unproven proximity should return to the auth proximity menu."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            side_effect=[MOCK_V2_DETECTION, MOCK_V2_DETECTION_PROXIMITY_NOT_PROVEN],
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_proximity"},
        )

        # User claims they opened the door but proximityProven is false
        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {"next_step_id": "auth_proximity_confirm"},
        )

        # Should return to the proximity menu
        assert result3["type"] == FlowResultType.MENU
        assert result3["step_id"] == "auth_proximity"


@pytest.mark.asyncio
async def test_proximity_switch_to_passphrase(hass: HomeAssistant) -> None:
    """User should be able to switch from proximity menu to passphrase."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_proximity"},
        )
        assert result2b["step_id"] == "auth_proximity"

        # User picks "Use passphrase instead"
        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )

        assert result3["type"] == FlowResultType.FORM
        assert result3["step_id"] == "auth_passphrase"


# ---------- duplicate entry prevention ----------


@pytest.mark.asyncio
async def test_duplicate_entry_aborts(hass: HomeAssistant) -> None:
    """Setting up a panel that is already configured should abort."""
    existing = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "existing-token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    existing.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


# ---------- zeroconf edge cases ----------


@pytest.mark.asyncio
async def test_zeroconf_non_ipv4_aborts(hass: HomeAssistant) -> None:
    """Non-IPv4 discovery addresses should abort."""

    discovery_info = ZeroconfServiceInfo(
        ip_address=ipaddress.IPv6Address("fe80::1"),
        ip_addresses=[ipaddress.IPv6Address("fe80::1")],
        hostname="span-panel.local.",
        name="SPAN Panel._ebus._tcp.local.",
        port=8883,
        properties={},
        type="_ebus._tcp.local.",
    )

    with patch(
        "homeassistant.components.span_panel.config_flow.is_ipv4_address",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "not_ipv4_address"


@pytest.mark.asyncio
async def test_zeroconf_already_configured_aborts(hass: HomeAssistant) -> None:
    """Zeroconf discovery of an already-configured host should abort."""
    existing = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: "192.168.1.200",
            CONF_ACCESS_TOKEN: "existing-token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    existing.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address=ipaddress.IPv4Address("192.168.1.200"),
        ip_addresses=[ipaddress.IPv4Address("192.168.1.200")],
        hostname="span-panel.local.",
        name="SPAN Panel._ebus._tcp.local.",
        port=8883,
        properties={},
        type="_ebus._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT


@pytest.mark.asyncio
async def test_zeroconf_not_span_panel_aborts(hass: HomeAssistant) -> None:
    """Zeroconf discovery where v2 endpoint does not respond should abort."""

    # Detection returns v1 (not v2) — this IP is not a valid v2 panel
    mock_bad_detection = DetectionResult(
        api_version="v1",
        status_info=None,
    )

    discovery_info = ZeroconfServiceInfo(
        ip_address=ipaddress.IPv4Address("192.168.1.200"),
        ip_addresses=[ipaddress.IPv4Address("192.168.1.200")],
        hostname="span-panel.local.",
        name="SPAN Panel._ebus._tcp.local.",
        port=8883,
        properties={},
        type="_ebus._tcp.local.",
    )

    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=mock_bad_detection,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.is_ipv4_address",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "not_span_panel"


@pytest.mark.usefixtures("socket_enabled")
@pytest.mark.asyncio
async def test_zeroconf_end_to_end_entry_creation(hass: HomeAssistant) -> None:
    """Zeroconf discovery through confirm → passphrase → naming → entry creation."""

    discovery_info = ZeroconfServiceInfo(
        ip_address=ipaddress.IPv4Address("192.168.1.200"),
        ip_addresses=[ipaddress.IPv4Address("192.168.1.200")],
        hostname="span-panel.local.",
        name="SPAN Panel._ebus._tcp.local.",
        port=8883,
        properties={},
        type="_ebus._tcp.local.",
    )

    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.is_ipv4_address",
            return_value=True,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_passphrase",
            return_value=MOCK_V2_AUTH,
        ),
    ):
        # Step 1: zeroconf discovery → confirm
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm_discovery"

        # Step 2: confirm → auth choice
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        assert result2["type"] == FlowResultType.MENU
        assert result2["step_id"] == "choose_v2_auth"

        # Step 3: choose passphrase
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )
        assert result3["step_id"] == "auth_passphrase"

        # Step 4: enter passphrase
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {CONF_HOP_PASSPHRASE: MOCK_PASSPHRASE},
        )
        assert result4["step_id"] == "choose_entity_naming_initial"

        # Step 5: accept naming default → entry created
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            {"entity_naming_pattern": "friendly_names"},
        )
        assert result5["type"] == FlowResultType.CREATE_ENTRY
        assert result5["data"][CONF_API_VERSION] == "v2"
        assert result5["data"][CONF_HOST] == "192.168.1.200"


# ---------- reauth: proximity ----------


@pytest.mark.asyncio
async def test_reauth_v2_proximity_success(hass: HomeAssistant) -> None:
    """Reauth via proximity should update credentials."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "old-token",
            CONF_API_VERSION: "v2",
            CONF_EBUS_BROKER_HOST: "old-host",
            CONF_EBUS_BROKER_PORT: 8883,
            CONF_EBUS_BROKER_USERNAME: "old-user",
            CONF_EBUS_BROKER_PASSWORD: "old-pass",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            side_effect=[MOCK_V2_DETECTION, MOCK_V2_DETECTION_PROXIMITY_PROVEN],
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_proximity",
            return_value=MOCK_V2_AUTH,
        ),
        patch.object(hass.config_entries, "async_reload", return_value=True),
    ):
        result = await entry.start_reauth_flow(hass)
        assert result["step_id"] == "choose_v2_auth"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "auth_proximity"},
        )
        assert result2["step_id"] == "auth_proximity"

        # User confirms door challenge
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_proximity_confirm"},
        )

        assert result3["type"] == FlowResultType.ABORT
        assert result3["reason"] == "reauth_successful"

    assert entry.data[CONF_ACCESS_TOKEN] == "v2-token-abc"
    assert entry.data[CONF_EBUS_BROKER_USERNAME] == "span-user"


# ---------- reconfigure ----------


@pytest.mark.asyncio
async def test_reconfigure_shows_current_host(hass: HomeAssistant) -> None:
    """Reconfigure step should pre-fill the current host."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


@pytest.mark.asyncio
async def test_reconfigure_success(hass: HomeAssistant) -> None:
    """Reconfigure should update the host and reload."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    new_host = "192.168.1.200"

    with patch(
        "homeassistant.components.span_panel.config_flow.detect_api_version",
        return_value=MOCK_V2_DETECTION,
    ):
        result = await entry.start_reconfigure_flow(hass)

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: new_host},
        )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "reconfigure_successful"

    assert entry.data[CONF_HOST] == new_host
    # Other data should be preserved
    assert entry.data[CONF_ACCESS_TOKEN] == "token"
    assert entry.data[CONF_API_VERSION] == "v2"


@pytest.mark.asyncio
async def test_reconfigure_unreachable_host(hass: HomeAssistant) -> None:
    """Reconfigure with unreachable host should show cannot_connect error."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.span_panel.config_flow.detect_api_version",
        side_effect=SpanPanelConnectionError("timeout"),
    ):
        result = await entry.start_reconfigure_flow(hass)

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "10.0.0.99"},
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "reconfigure"
        assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_reconfigure_different_panel_aborts(hass: HomeAssistant) -> None:
    """Reconfigure to a different panel serial should abort with unique_id_mismatch."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.span_panel.config_flow.detect_api_version",
        return_value=MOCK_V2_DETECTION_OTHER,
    ):
        result = await entry.start_reconfigure_flow(hass)

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.250"},
        )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "unique_id_mismatch"


@pytest.mark.asyncio
async def test_reconfigure_empty_host(hass: HomeAssistant) -> None:
    """Reconfigure with empty host should re-show with host_required error."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "   "},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {"base": "host_required"}


@pytest.mark.asyncio
async def test_reconfigure_recovery_after_error(hass: HomeAssistant) -> None:
    """User can successfully reconfigure after an initial connection error."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.span_panel.config_flow.detect_api_version",
        side_effect=[SpanPanelConnectionError("timeout"), MOCK_V2_DETECTION],
    ):
        result = await entry.start_reconfigure_flow(hass)

        # First attempt: connection error
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "10.0.0.99"},
        )
        assert result2["errors"] == {"base": "cannot_connect"}

        # Second attempt: success
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_HOST: "192.168.1.200"},
        )
        assert result3["type"] == FlowResultType.ABORT
        assert result3["reason"] == "reconfigure_successful"

    assert entry.data[CONF_HOST] == "192.168.1.200"


# ---------- hassio (Supervisor) discovery ----------


MOCK_HASSIO_CONFIG = {
    "host": "192.168.1.50",
    "port": 9090,
    "serial": "SPAN-SIM-001",
}

MOCK_V2_DETECTION_SIM = DetectionResult(
    api_version="v2",
    status_info=V2StatusInfo(
        serial_number="SPAN-SIM-001",
        firmware_version="2.0.0",
    ),
)


def _hassio_service_info(config: dict[str, str | int]) -> HassioServiceInfo:
    """Build a HassioServiceInfo for testing."""
    return HassioServiceInfo(
        config=config,
        name="SPAN Panel Simulator",
        slug="span_panel_simulator",
        uuid="test-uuid-1234",
    )


@pytest.mark.asyncio
async def test_hassio_missing_host_aborts(hass: HomeAssistant) -> None:
    """Hassio discovery with no host should abort with no_host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=_hassio_service_info({"port": 9090, "serial": "SPAN-SIM-001"}),
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_host"


@pytest.mark.asyncio
async def test_hassio_missing_host_empty_string_aborts(hass: HomeAssistant) -> None:
    """Hassio discovery with empty host string should abort with no_host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=_hassio_service_info({"host": "", "port": 9090, "serial": "SPAN-SIM-001"}),
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_host"


@pytest.mark.asyncio
async def test_hassio_not_v2_aborts(hass: HomeAssistant) -> None:
    """Hassio discovery of a non-v2 panel should abort with not_span_panel."""
    with patch(
        "homeassistant.components.span_panel.config_flow.detect_api_version",
        return_value=MOCK_V1_DETECTION,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HASSIO},
            data=_hassio_service_info(MOCK_HASSIO_CONFIG),
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_span_panel"


@pytest.mark.asyncio
async def test_hassio_no_serial_aborts(hass: HomeAssistant) -> None:
    """Hassio discovery where panel returns no serial should abort."""
    detection_no_serial = DetectionResult(
        api_version="v2",
        status_info=V2StatusInfo(
            serial_number="",
            firmware_version="2.0.0",
        ),
    )
    config_no_serial = {"host": "192.168.1.50", "port": 9090, "serial": ""}

    with patch(
        "homeassistant.components.span_panel.config_flow.detect_api_version",
        return_value=detection_no_serial,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HASSIO},
            data=_hassio_service_info(config_no_serial),
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_serial"


@pytest.mark.asyncio
async def test_hassio_discovery_routes_to_confirm(hass: HomeAssistant) -> None:
    """Successful hassio discovery should route to confirm_discovery."""
    with patch(
        "homeassistant.components.span_panel.config_flow.detect_api_version",
        return_value=MOCK_V2_DETECTION_SIM,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HASSIO},
            data=_hassio_service_info(MOCK_HASSIO_CONFIG),
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm_discovery"


@pytest.mark.asyncio
async def test_hassio_dedup_by_serial(hass: HomeAssistant) -> None:
    """Hassio discovery of an already-configured serial should abort and update host/port."""
    existing = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: "192.168.1.40",
            CONF_ACCESS_TOKEN: "existing-token",
            CONF_API_VERSION: "v2",
            CONF_HTTP_PORT: 80,
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-SIM-001",
    )
    existing.add_to_hass(hass)

    with patch(
        "homeassistant.components.span_panel.config_flow.detect_api_version",
        return_value=MOCK_V2_DETECTION_SIM,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HASSIO},
            data=_hassio_service_info(MOCK_HASSIO_CONFIG),
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Host and port should be updated to the new values
    assert existing.data[CONF_HOST] == "192.168.1.50"
    assert existing.data[CONF_HTTP_PORT] == 9090


@pytest.mark.usefixtures("socket_enabled")
@pytest.mark.asyncio
async def test_hassio_end_to_end_entry_creation(hass: HomeAssistant) -> None:
    """Hassio discovery through confirm -> passphrase -> naming -> entry creation."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION_SIM,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_passphrase",
            return_value=MOCK_V2_AUTH,
        ),
    ):
        # Step 1: hassio discovery -> confirm
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HASSIO},
            data=_hassio_service_info(MOCK_HASSIO_CONFIG),
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm_discovery"

        # Step 2: confirm -> auth choice
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        assert result2["type"] == FlowResultType.MENU
        assert result2["step_id"] == "choose_v2_auth"

        # Step 3: choose passphrase
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )
        assert result3["step_id"] == "auth_passphrase"

        # Step 4: enter passphrase
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {CONF_HOP_PASSPHRASE: MOCK_PASSPHRASE},
        )
        assert result4["step_id"] == "choose_entity_naming_initial"

        # Step 5: accept naming default -> entry created
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            {"entity_naming_pattern": "friendly_names"},
        )
        assert result5["type"] == FlowResultType.CREATE_ENTRY
        assert result5["data"][CONF_API_VERSION] == "v2"
        assert result5["data"][CONF_HOST] == "192.168.1.50"
        assert result5["data"][CONF_HTTP_PORT] == 9090


# ---------- user flow: null status_info ----------


@pytest.mark.asyncio
async def test_user_flow_v2_null_status_info_shows_error(hass: HomeAssistant) -> None:
    """User flow should show cannot_connect when v2 detection has null status_info."""
    detection_no_status = DetectionResult(
        api_version="v2",
        status_info=None,
    )

    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=detection_no_status,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "user"
        assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_reauth_v2_null_status_info_aborts(hass: HomeAssistant) -> None:
    """Reauth should abort with cannot_connect when v2 detection has null status_info."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "old-token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    detection_no_status = DetectionResult(
        api_version="v2",
        status_info=None,
    )

    with patch(
        "homeassistant.components.span_panel.config_flow.detect_api_version",
        return_value=detection_no_status,
    ):
        result = await entry.start_reauth_flow(hass)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.asyncio
async def test_zeroconf_invalid_http_port_defaults_to_80(hass: HomeAssistant) -> None:
    """Invalid httpPort TXT records should fall back to port 80."""

    discovery_info = ZeroconfServiceInfo(
        ip_address=ipaddress.IPv4Address("192.168.1.200"),
        ip_addresses=[ipaddress.IPv4Address("192.168.1.200")],
        hostname="span-panel.local.",
        name="SPAN Panel._ebus._tcp.local.",
        port=8883,
        properties={"httpPort": "bad-port"},
        type="_ebus._tcp.local.",
    )

    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.get_async_client",
            return_value=fake_client,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ) as mock_detect,
        patch(
            "homeassistant.components.span_panel.config_flow.is_ipv4_address",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm_discovery"
    mock_detect.assert_awaited_once_with(
        "192.168.1.200", port=80, httpx_client=fake_client
    )


@pytest.mark.usefixtures("socket_enabled")
@pytest.mark.asyncio
async def test_user_flow_fqdn_registration_progress_then_naming(
    hass: HomeAssistant,
) -> None:
    """FQDN hosts should route through the registration progress step."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_passphrase",
            return_value=MOCK_V2_AUTH,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.register_fqdn",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.check_fqdn_tls_ready",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "panel.example.com"},
        )
        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )
        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {CONF_HOP_PASSPHRASE: MOCK_PASSPHRASE},
        )
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_REGISTERED_FQDN] == "panel.example.com"


@pytest.mark.usefixtures("socket_enabled")
@pytest.mark.asyncio
async def test_user_flow_fqdn_registration_failure_can_continue(
    hass: HomeAssistant,
) -> None:
    """Failed FQDN registration should allow continuing without registration."""
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_passphrase",
            return_value=MOCK_V2_AUTH,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.register_fqdn",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.check_fqdn_tls_ready",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "panel.example.com"},
        )
        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )
        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {CONF_HOP_PASSPHRASE: MOCK_PASSPHRASE},
        )
        assert result3["type"] == FlowResultType.FORM
        assert result3["step_id"] == "choose_entity_naming_initial"


@pytest.mark.usefixtures("socket_enabled")
@pytest.mark.asyncio
async def test_fqdn_entry_creation_sets_registered_fqdn_and_unique_title(
    hass: HomeAssistant,
) -> None:
    """FQDN-based entries should store the registered host and keep unique titles."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="Span Panel",
        data={CONF_HOST: "192.168.1.10", CONF_ACCESS_TOKEN: "existing-token"},
        unique_id="EXISTING-PANEL-001",
    )
    existing.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_host",
            return_value=True,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.validate_v2_passphrase",
            return_value=MOCK_V2_AUTH,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.register_fqdn",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.check_fqdn_tls_ready",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.span_panel.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "panel.example.com", CONF_HTTP_PORT: 8080},
        )
        result2b = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"next_step_id": "auth_passphrase"},
        )
        result3 = await hass.config_entries.flow.async_configure(
            result2b["flow_id"],
            {CONF_HOP_PASSPHRASE: MOCK_PASSPHRASE},
        )
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Span Panel 2"
    assert result3["data"][CONF_HOST] == "panel.example.com"
    assert result3["data"][CONF_REGISTERED_FQDN] == "panel.example.com"
    assert result3["data"][CONF_HTTP_PORT] == 8080


@pytest.mark.asyncio
async def test_update_v2_entry_missing_entry_aborts_with_reauth_failed(
    hass: HomeAssistant,
) -> None:
    """Missing entries during reauth should abort cleanly."""
    flow = SpanPanelConfigFlow()
    flow.hass = hass
    flow.trigger_flow_type = TriggerFlowType.UPDATE_ENTRY
    flow.context = {"entry_id": "missing-entry"}
    flow.host = MOCK_HOST
    flow.serial_number = "SPAN-V2-001"
    flow.access_token = MOCK_V2_AUTH.access_token
    flow._is_flow_setup = True
    flow._store_v2_auth_result(MOCK_V2_AUTH, MOCK_PASSPHRASE)

    result = await flow._async_finalize_v2_auth()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_failed"


@pytest.mark.asyncio
async def test_reconfigure_to_fqdn_registers_and_updates_registered_fqdn(
    hass: HomeAssistant,
) -> None:
    """Reconfiguring to an FQDN should go through registration and persist it."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "token",
            CONF_API_VERSION: "v2",
            CONF_EBUS_BROKER_PORT: 8883,
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.register_fqdn",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.check_fqdn_tls_ready",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        result = await entry.start_reconfigure_flow(hass)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "panel.example.com"},
        )
        result3 = result2

    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "panel.example.com"
    assert entry.data[CONF_REGISTERED_FQDN] == "panel.example.com"


@pytest.mark.asyncio
async def test_reconfigure_fqdn_failure_can_continue_without_registration(
    hass: HomeAssistant,
) -> None:
    """Failed FQDN registration during reconfigure should allow continue."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_ACCESS_TOKEN: "token",
            CONF_API_VERSION: "v2",
            CONF_EBUS_BROKER_PORT: 8883,
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.register_fqdn",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.check_fqdn_tls_ready",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        result = await entry.start_reconfigure_flow(hass)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "panel.example.com"},
        )
        result4 = result2

    assert result4["type"] == FlowResultType.ABORT
    assert result4["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "panel.example.com"
    assert CONF_REGISTERED_FQDN not in entry.data


@pytest.mark.asyncio
async def test_reconfigure_switch_from_fqdn_to_ip_clears_registration(
    hass: HomeAssistant,
) -> None:
    """Switching from FQDN back to IP should delete the old registration."""
    entry = MockConfigEntry(
        version=3,
        minor_version=1,
        domain=DOMAIN,
        title="Span Panel",
        data={
            CONF_HOST: "panel.example.com",
            CONF_REGISTERED_FQDN: "panel.example.com",
            CONF_ACCESS_TOKEN: "token",
            CONF_API_VERSION: "v2",
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="SPAN-V2-001",
    )
    entry.add_to_hass(hass)

    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow.get_async_client",
            return_value=fake_client,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.detect_api_version",
            return_value=MOCK_V2_DETECTION,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow.delete_fqdn",
            new=AsyncMock(),
        ) as mock_delete,
    ):
        result = await entry.start_reconfigure_flow(hass)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.201"},
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    mock_delete.assert_awaited_once_with(
        "192.168.1.201", "token", port=80, httpx_client=fake_client
    )
    assert entry.data[CONF_HOST] == "192.168.1.201"
    assert entry.data[CONF_REGISTERED_FQDN] == ""
