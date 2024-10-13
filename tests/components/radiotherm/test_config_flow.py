"""Test the Radio Thermostat config flow."""

from unittest.mock import MagicMock, patch

from radiotherm import CommonThermostat
from radiotherm.validate import RadiothermTstatError

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.radiotherm.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _mock_radiotherm():
    tstat = MagicMock(autospec=CommonThermostat)
    tstat.name = {"raw": "My Name"}
    tstat.sys = {
        "raw": {"uuid": "aabbccddeeff", "fw_version": "1.2.3", "api_version": "4.5.6"}
    }
    tstat.model = {"raw": "Model"}
    return tstat


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.radiotherm.data.radiotherm.get_thermostat",
            return_value=_mock_radiotherm(),
        ),
        patch(
            "homeassistant.components.radiotherm.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.2.3.4",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My Name"
    assert result2["data"] == {
        "host": "1.2.3.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.radiotherm.data.radiotherm.get_thermostat",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.2.3.4",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.radiotherm.data.radiotherm.get_thermostat",
        side_effect=RadiothermTstatError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.2.3.4",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_HOST: "cannot_connect"}


async def test_dhcp_can_confirm(hass: HomeAssistant) -> None:
    """Test DHCP discovery flow can confirm right away."""

    with patch(
        "homeassistant.components.radiotherm.data.radiotherm.get_thermostat",
        return_value=_mock_radiotherm(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                hostname="radiotherm",
                ip="1.2.3.4",
                macaddress="aabbccddeeff",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "host": "1.2.3.4",
        "name": "My Name",
        "model": "Model",
    }

    with patch(
        "homeassistant.components.radiotherm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My Name"
    assert result2["data"] == {
        "host": "1.2.3.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_fails_to_connect(hass: HomeAssistant) -> None:
    """Test DHCP discovery flow that fails to connect."""

    with patch(
        "homeassistant.components.radiotherm.data.radiotherm.get_thermostat",
        side_effect=RadiothermTstatError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                hostname="radiotherm",
                ip="1.2.3.4",
                macaddress="aabbccddeeff",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_dhcp_already_exists(hass: HomeAssistant) -> None:
    """Test DHCP discovery flow that fails to connect."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.radiotherm.data.radiotherm.get_thermostat",
        return_value=_mock_radiotherm(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                hostname="radiotherm",
                ip="1.2.3.4",
                macaddress="aabbccddeeff",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_unique_id_already_exists(hass: HomeAssistant) -> None:
    """Test creating an entry where the unique_id already exists."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.radiotherm.data.radiotherm.get_thermostat",
            return_value=_mock_radiotherm(),
        ),
        patch(
            "homeassistant.components.radiotherm.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.2.3.4",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
