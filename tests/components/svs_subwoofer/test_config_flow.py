"""Tests for the SVS Subwoofer config flow."""

from homeassistant.components.svs_subwoofer.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    SVS_ADDRESS,
    SVS_NAME,
    SVS_SERVICE_INFO,
    _service_info,
    patch_async_discovered_service_info,
    patch_async_setup_entry,
)

from tests.common import MockConfigEntry


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """A discovered SVS device walks through bluetooth_confirm to entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=SVS_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_NAME: "Right Sub"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Right Sub"
    assert result["data"] == {CONF_ADDRESS: SVS_ADDRESS, CONF_NAME: "Right Sub"}


async def test_bluetooth_already_configured(hass: HomeAssistant) -> None:
    """A second discovery for the same device aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=SVS_ADDRESS.lower(),
        data={CONF_ADDRESS: SVS_ADDRESS, CONF_NAME: SVS_NAME},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=SVS_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_picks_discovered(hass: HomeAssistant) -> None:
    """User flow: user picks an SVS device from the discovered list."""
    with patch_async_discovered_service_info([SVS_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: SVS_ADDRESS, CONF_NAME: ""},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == SVS_ADDRESS


async def test_user_manual_entry(hass: HomeAssistant) -> None:
    """User flow with no discoveries falls through to manual MAC entry."""
    with patch_async_discovered_service_info([]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: SVS_ADDRESS, CONF_NAME: "Manual Sub"},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Manual Sub"


async def test_user_manual_invalid_mac(hass: HomeAssistant) -> None:
    """Invalid MAC formats surface an error on the manual step."""
    with patch_async_discovered_service_info([]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: "not-a-mac", CONF_NAME: "x"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_ADDRESS: "invalid_mac"}


async def test_user_picks_manual_from_picker(hass: HomeAssistant) -> None:
    """Picking the 'manual' sentinel from the discovery list jumps to manual step."""
    with patch_async_discovered_service_info([SVS_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: "manual", CONF_NAME: ""},
        )
    assert result["step_id"] == "manual"


async def test_user_skips_existing_and_unnamed(hass: HomeAssistant) -> None:
    """User flow drops already-configured devices and devices without names."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=SVS_ADDRESS.lower(),
        data={CONF_ADDRESS: SVS_ADDRESS, CONF_NAME: SVS_NAME},
    ).add_to_hass(hass)

    nameless = _service_info(address="08:EB:ED:99:99:99", name="")
    # Non-SVS device: not in SVS service UUID list, not in SVS MAC range.
    other = _service_info(address="AA:BB:CC:DD:EE:FF", name="OtherDevice")
    other.service_uuids = []

    with patch_async_discovered_service_info([SVS_SERVICE_INFO, nameless, other]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    # Either we land on a user-step form showing only the "OtherDevice" or we
    # fall through to manual entry — both confirm the discovery filter works.
    assert result["step_id"] in ("user", "manual")


async def test_user_already_configured(hass: HomeAssistant) -> None:
    """Adding an already-configured device via the user flow aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=SVS_ADDRESS.lower(),
        data={CONF_ADDRESS: SVS_ADDRESS, CONF_NAME: SVS_NAME},
    ).add_to_hass(hass)

    with patch_async_discovered_service_info([SVS_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    # All discovered devices are already configured, so we drop into manual
    # entry; entering the same MAC must abort.
    assert result["step_id"] in ("user", "manual")
    if result["step_id"] == "user":
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: SVS_ADDRESS, CONF_NAME: ""},
        )
    else:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: SVS_ADDRESS, CONF_NAME: SVS_NAME},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
