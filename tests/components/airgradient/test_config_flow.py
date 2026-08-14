"""Tests for the AirGradient config flow."""

from dataclasses import replace
from ipaddress import ip_address
from unittest.mock import ANY, AsyncMock, patch

from airgradient import (
    AirGradientBusyError,
    AirGradientConnectionError,
    AirGradientError,
    AirGradientParseError,
    ApiVersion,
    ConfigurationControl,
)
import pytest

from homeassistant.components.airgradient.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import load_measures_fixture

from tests.common import MockConfigEntry

OLD_ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("10.0.0.131"),
    ip_addresses=[ip_address("10.0.0.131")],
    hostname="airgradient_84fce612f5b8.local.",
    name="airgradient_84fce612f5b8._airgradient._tcp.local.",
    port=80,
    type="_airgradient._tcp.local.",
    properties={
        "vendor": "AirGradient",
        "fw_ver": "3.0.8",
        "serialno": "84fce612f5b8",
        "model": "I-9PSL",
    },
)

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("10.0.0.131"),
    ip_addresses=[ip_address("10.0.0.131")],
    hostname="airgradient_84fce612f5b8.local.",
    name="airgradient_84fce612f5b8._airgradient._tcp.local.",
    port=80,
    type="_airgradient._tcp.local.",
    properties={
        "vendor": "AirGradient",
        "fw_ver": "3.1.1",
        "serialno": "84fce612f5b8",
        "model": "I-9PSL",
    },
)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(
    hass: HomeAssistant, mock_new_airgradient_client: AsyncMock
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "I-9PSL"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
    }
    assert result["result"].unique_id == "84fce612f5b8"
    mock_new_airgradient_client.set_configuration_control.assert_awaited_once_with(
        ConfigurationControl.LOCAL
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_with_registered_device(
    hass: HomeAssistant, mock_cloud_airgradient_client: AsyncMock
) -> None:
    """Test we don't revert the cloud setting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "84fce612f5b8"
    mock_cloud_airgradient_client.set_configuration_control.assert_not_called()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_errors(
    hass: HomeAssistant, mock_airgradient_client: AsyncMock
) -> None:
    """Test flow errors."""
    mock_airgradient_client.get_current_measures.side_effect = (
        AirGradientConnectionError()
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_airgradient_client.get_current_measures.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("method", "exception"),
    [
        ("get_config", AirGradientConnectionError()),
        (
            "set_configuration_control",
            AirGradientBusyError(status=503, code="busy"),
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_config_source_errors(
    hass: HomeAssistant,
    mock_v1_airgradient_client: AsyncMock,
    method: str,
    exception: AirGradientError,
) -> None:
    """Test errors while setting the configuration source."""
    getattr(mock_v1_airgradient_client, method).side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    getattr(mock_v1_airgradient_client, method).side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_old_firmware_version(
    hass: HomeAssistant, mock_airgradient_client: AsyncMock
) -> None:
    """Test flow with old firmware version."""
    mock_airgradient_client.get_current_measures.side_effect = AirGradientParseError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_version"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow(
    hass: HomeAssistant, mock_new_airgradient_client: AsyncMock
) -> None:
    """Test zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "I-9PSL"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
    }
    assert result["result"].unique_id == "84fce612f5b8"
    mock_new_airgradient_client.set_configuration_control.assert_awaited_once_with(
        ConfigurationControl.LOCAL
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_cloud_device(
    hass: HomeAssistant, mock_cloud_airgradient_client: AsyncMock
) -> None:
    """Test zeroconf flow doesn't revert the cloud setting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_cloud_airgradient_client.set_configuration_control.assert_not_called()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_config_source_error(
    hass: HomeAssistant, mock_new_airgradient_client: AsyncMock
) -> None:
    """Test errors while setting the discovered device configuration source."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    mock_new_airgradient_client.set_configuration_control.side_effect = (
        AirGradientBusyError(status=503, code="busy")
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_new_airgradient_client.set_configuration_control.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_flow_abort_old_firmware(
    hass: HomeAssistant, mock_airgradient_client: AsyncMock
) -> None:
    """Test zeroconf flow aborts with old firmware."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=OLD_ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_version"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_v1_hint(
    hass: HomeAssistant,
) -> None:
    """Test zeroconf V1 hint seeds the client and skips the legacy gate."""
    discovery_info = replace(
        ZEROCONF_DISCOVERY,
        properties={
            **ZEROCONF_DISCOVERY.properties,
            "api": "1",
            "fw_ver": "1.0.0",
            "model": "P-1PSG",
        },
    )
    with patch(
        "homeassistant.components.airgradient.config_flow.AirGradientClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.api_version = ApiVersion.V1
        client.get_current_measures.return_value = load_measures_fixture(
            "measures_v1_full.json", ApiVersion.V1
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=discovery_info,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    mock_client.assert_called_once_with(
        "10.0.0.131", session=ANY, api_version=ApiVersion.V1
    )


@pytest.mark.parametrize("api", [None, "2"])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_probes_for_missing_or_unknown_api_hint(
    hass: HomeAssistant, api: str | None
) -> None:
    """Test missing and unknown API hints leave the client unseeded."""
    properties = dict(ZEROCONF_DISCOVERY.properties)
    if api is None:
        properties.pop("api", None)
    else:
        properties["api"] = api
    discovery_info = replace(ZEROCONF_DISCOVERY, properties=properties)
    with patch(
        "homeassistant.components.airgradient.config_flow.AirGradientClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.api_version = ApiVersion.LEGACY
        client.get_current_measures.return_value = load_measures_fixture(
            "current_measures_indoor.json"
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=discovery_info,
        )

    assert result["type"] is FlowResultType.FORM
    mock_client.assert_called_once_with("10.0.0.131", session=ANY)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_stale_v1_hint_applies_legacy_gate(
    hass: HomeAssistant,
) -> None:
    """Test a stale V1 hint still enforces the legacy minimum firmware."""
    discovery_info = replace(
        OLD_ZEROCONF_DISCOVERY,
        properties={**OLD_ZEROCONF_DISCOVERY.properties, "api": "1"},
    )
    with patch(
        "homeassistant.components.airgradient.config_flow.AirGradientClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.api_version = ApiVersion.LEGACY
        client.get_current_measures.return_value = load_measures_fixture(
            "current_measures_indoor.json"
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=discovery_info,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_version"
    mock_client.assert_called_once_with(
        "10.0.0.131", session=ANY, api_version=ApiVersion.V1
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_aborts_on_serial_mismatch(
    hass: HomeAssistant, mock_airgradient_client: AsyncMock
) -> None:
    """Test zeroconf serial must match the measures serial."""
    discovery_info = replace(
        ZEROCONF_DISCOVERY,
        properties={
            **ZEROCONF_DISCOVERY.properties,
            "serialno": "84fce612f5b9",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_mismatch"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_v1_skips_legacy_firmware_gate(
    hass: HomeAssistant, mock_v1_airgradient_client: AsyncMock
) -> None:
    """Test manual setup skips the legacy firmware minimum for an API V1 capable model."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_legacy_firmware_gate(
    hass: HomeAssistant, mock_airgradient_client: AsyncMock
) -> None:
    """Test manual legacy setup enforces the minimum firmware version."""
    mock_airgradient_client.get_current_measures.return_value.firmware_version = "3.0.8"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_version"


async def test_zeroconf_flow_abort_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test zeroconf flow aborts with duplicate."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_works_discovery(
    hass: HomeAssistant, mock_new_airgradient_client: AsyncMock
) -> None:
    """Test user flow can continue after discovery happened."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert len(hass.config_entries.flow.async_progress(DOMAIN)) == 2
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify the discovery flow was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_new_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "10.0.0.131",
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_new_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)
    mock_new_airgradient_client.get_current_measures.side_effect = (
        AirGradientConnectionError()
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.132"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_new_airgradient_client.get_current_measures.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.132"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "10.0.0.132",
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_new_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow aborts with unique id mismatch."""
    mock_config_entry.add_to_hass(hass)

    mock_new_airgradient_client.get_current_measures.return_value.serial_number = (
        "84fce612f5b9"
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.132"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == {
        CONF_HOST: "10.0.0.131",
    }
