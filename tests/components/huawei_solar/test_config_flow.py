"""Test the Fronius config flow."""
from unittest.mock import Mock, patch

from huawei_solar import (
    AsyncHuaweiSolar,
    ConnectionException,
    HuaweiSolarException,
    ReadException,
    Result,
)

from homeassistant import config_entries
from homeassistant.components.huawei_solar.const import CONF_SLAVE_IDS, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test manual device add with default pin."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    inverter = Mock(spec=AsyncHuaweiSolar)

    inverter.get_multiple.return_value = [
        Result("MOCK_MODEL_NAME", None),
        Result("MOCK_SN", None),
    ]

    with patch("huawei_solar.AsyncHuaweiSolar.create", return_value=inverter,), patch(
        "homeassistant.components.huawei_solar.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 502, CONF_SLAVE_IDS: "0,1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "MOCK_MODEL_NAME"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 502,
        CONF_SLAVE_IDS: [0, 1],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_connection_error(hass: HomeAssistant) -> None:
    """Test manual device add with default pin."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "huawei_solar.AsyncHuaweiSolar.create",
        side_effect=ConnectionException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 502, CONF_SLAVE_IDS: "0"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_read_error(hass: HomeAssistant) -> None:
    """Test manual device add with default pin."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "huawei_solar.AsyncHuaweiSolar.create",
        side_effect=ReadException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 502, CONF_SLAVE_IDS: "0"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "read_error"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test manual device add with default pin."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "huawei_solar.AsyncHuaweiSolar.create",
        side_effect=HuaweiSolarException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 502, CONF_SLAVE_IDS: "0"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_invalid_slave_ids(hass: HomeAssistant) -> None:
    """Test manual device add with default pin."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1", CONF_PORT: 502, CONF_SLAVE_IDS: "0,a"},
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_slave_ids"}


async def test_form_invalid_extra_slave(hass: HomeAssistant) -> None:
    """Test manual device add with default pin."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    def _get_multiple(names: list[str], slave=None):
        if slave is None:
            return [
                Result("MOCK_MODEL_NAME", None),
                Result("MOCK_SN", None),
            ]
        else:
            raise HuaweiSolarException("Invalid extra slave")

    inverter = Mock(spec=AsyncHuaweiSolar)

    with patch(
        "huawei_solar.AsyncHuaweiSolar.create",
        return_value=inverter,
    ), patch.object(
        inverter,
        "get_multiple",
    ) as mock_get_multiple:
        mock_get_multiple.side_effect = _get_multiple

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 502, CONF_SLAVE_IDS: "0,1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "slave_cannot_connect"}


async def test_form_already_configured(hass, aioclient_mock):
    """Test if a inverter has already been configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="MOCK_SN",
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 502, CONF_SLAVE_IDS: [0]},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    inverter = Mock(spec=AsyncHuaweiSolar)

    inverter.get_multiple.return_value = [
        Result("MOCK_MODEL_NAME", None),
        Result("MOCK_SN", None),
    ]

    with patch("huawei_solar.AsyncHuaweiSolar.create", return_value=inverter):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 502, CONF_SLAVE_IDS: "0"},
        )

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"
