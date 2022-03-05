"""Test the KDEConnect config flow."""
from unittest.mock import patch

from pykdeconnect.const import PairingResult

from homeassistant import config_entries
from homeassistant.components.kdeconnect.const import (
    CONF_DEVICE_CERT,
    CONF_DEVICE_INCOMING_CAPS,
    CONF_DEVICE_NAME,
    CONF_DEVICE_OUTGOING_CAPS,
    CONF_DEVICE_TYPE,
    CONF_REFRESH,
    DATA_KEY_CLIENT,
    DOMAIN,
)
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.components.kdeconnect import (
    EXAMPLE_DEVICE_CERT,
    EXAMPLE_DEVICE_ID,
    EXAMPLE_DEVICE_IN_CAPS,
    EXAMPLE_DEVICE_NAME,
    EXAMPLE_DEVICE_OUT_CAPS,
    EXAMPLE_DEVICE_TYPE,
    _create_mocked_client,
    _create_mocked_device,
)


async def test_full_flow(hass: HomeAssistant) -> None:
    """Test a full config flow."""
    device = _create_mocked_device(PairingResult.ACCEPTED)
    client = _create_mocked_client([device])
    client.pairable_devices = [device]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_KEY_CLIENT] = client

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.kdeconnect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_NAME: EXAMPLE_DEVICE_NAME,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == EXAMPLE_DEVICE_NAME
    assert result2["data"] == {
        CONF_DEVICE_NAME: EXAMPLE_DEVICE_NAME,
        CONF_DEVICE_ID: EXAMPLE_DEVICE_ID,
        CONF_DEVICE_TYPE: EXAMPLE_DEVICE_TYPE.value,
        CONF_DEVICE_INCOMING_CAPS: EXAMPLE_DEVICE_IN_CAPS,
        CONF_DEVICE_OUTGOING_CAPS: EXAMPLE_DEVICE_OUT_CAPS,
        CONF_DEVICE_CERT: EXAMPLE_DEVICE_CERT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_pair_rejected(hass: HomeAssistant) -> None:
    """Test a cofig flow where our peer rejects the connection."""
    device = _create_mocked_device(PairingResult.REJECTED)
    client = _create_mocked_client([device])
    client.pairable_devices = [device]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_KEY_CLIENT] = client

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_NAME: EXAMPLE_DEVICE_NAME,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "rejected"}


async def test_pair_timeout(hass: HomeAssistant) -> None:
    """Test a cofig flow where our peer neither accepts, nor rejects our connection."""
    device = _create_mocked_device(PairingResult.TIMEOUT)
    client = _create_mocked_client([device])
    client.pairable_devices = [device]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_KEY_CLIENT] = client

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_NAME: EXAMPLE_DEVICE_NAME,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "timeout"}


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test handling of unknown errors during connection to a device."""
    device = _create_mocked_device(PairingResult.ACCEPTED)
    client = _create_mocked_client([device])
    client.pairable_devices = [device]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_KEY_CLIENT] = client

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kdeconnect.config_flow.try_pair",
        side_effect=Exception(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_NAME: EXAMPLE_DEVICE_NAME,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_duplicate_name(hass: HomeAssistant) -> None:
    """Test handling of multiple devices with the same name."""
    device1 = _create_mocked_device(PairingResult.ACCEPTED)
    device2 = _create_mocked_device(PairingResult.ACCEPTED)
    device3 = _create_mocked_device(PairingResult.ACCEPTED)
    device2.device_id = "device_2"
    device3.device_id = "device_3"
    client = _create_mocked_client([device1, device2, device3])
    client.pairable_devices = [device1, device2, device3]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_KEY_CLIENT] = client

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.kdeconnect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_NAME: f"{EXAMPLE_DEVICE_NAME} (1)",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == EXAMPLE_DEVICE_NAME
    assert result2["data"] == {
        CONF_DEVICE_NAME: EXAMPLE_DEVICE_NAME,
        CONF_DEVICE_ID: "device_2",
        CONF_DEVICE_TYPE: EXAMPLE_DEVICE_TYPE.value,
        CONF_DEVICE_INCOMING_CAPS: EXAMPLE_DEVICE_IN_CAPS,
        CONF_DEVICE_OUTGOING_CAPS: EXAMPLE_DEVICE_OUT_CAPS,
        CONF_DEVICE_CERT: EXAMPLE_DEVICE_CERT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_advanced_options(hass: HomeAssistant) -> None:
    """Test more detailed display of names if advanced options are enabled."""
    device = _create_mocked_device(PairingResult.ACCEPTED)
    client = _create_mocked_client([device])
    client.pairable_devices = [device]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_KEY_CLIENT] = client

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.kdeconnect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_NAME: f"{EXAMPLE_DEVICE_NAME} ({EXAMPLE_DEVICE_ID})",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == EXAMPLE_DEVICE_NAME
    assert result2["data"] == {
        CONF_DEVICE_NAME: EXAMPLE_DEVICE_NAME,
        CONF_DEVICE_ID: EXAMPLE_DEVICE_ID,
        CONF_DEVICE_TYPE: EXAMPLE_DEVICE_TYPE.value,
        CONF_DEVICE_INCOMING_CAPS: EXAMPLE_DEVICE_IN_CAPS,
        CONF_DEVICE_OUTGOING_CAPS: EXAMPLE_DEVICE_OUT_CAPS,
        CONF_DEVICE_CERT: EXAMPLE_DEVICE_CERT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_refresh(hass: HomeAssistant) -> None:
    """Test refreshing the device list."""
    device = _create_mocked_device(PairingResult.ACCEPTED)
    client = _create_mocked_client([device])
    client.pairable_devices = [device]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_KEY_CLIENT] = client

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_NAME: CONF_REFRESH,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] is None

    with patch(
        "homeassistant.components.kdeconnect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_NAME: EXAMPLE_DEVICE_NAME,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == EXAMPLE_DEVICE_NAME
    assert result3["data"] == {
        CONF_DEVICE_NAME: EXAMPLE_DEVICE_NAME,
        CONF_DEVICE_ID: EXAMPLE_DEVICE_ID,
        CONF_DEVICE_TYPE: EXAMPLE_DEVICE_TYPE.value,
        CONF_DEVICE_INCOMING_CAPS: EXAMPLE_DEVICE_IN_CAPS,
        CONF_DEVICE_OUTGOING_CAPS: EXAMPLE_DEVICE_OUT_CAPS,
        CONF_DEVICE_CERT: EXAMPLE_DEVICE_CERT,
    }
    assert len(mock_setup_entry.mock_calls) == 1
