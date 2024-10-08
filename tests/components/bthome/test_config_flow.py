"""Test the BTHome config flow."""

from unittest.mock import patch

from bthome_ble import BTHomeBluetoothDeviceData as DeviceData

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.bthome.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    NOT_BTHOME_SERVICE_INFO,
    PRST_SERVICE_INFO,
    TEMP_HUMI_ENCRYPTED_SERVICE_INFO,
    TEMP_HUMI_SERVICE_INFO,
)

from tests.common import MockConfigEntry


async def test_async_step_bluetooth_valid_device(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TEMP_HUMI_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    with patch("homeassistant.components.bthome.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "ATC 18B2"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "A4:C1:38:8D:18:B2"


async def test_async_step_bluetooth_during_onboarding(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth during onboarding."""
    with (
        patch(
            "homeassistant.components.bthome.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=False,
        ) as mock_onboarding,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=TEMP_HUMI_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ATC 18B2"
    assert result["data"] == {}
    assert result["result"].unique_id == "A4:C1:38:8D:18:B2"
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


async def test_async_step_bluetooth_valid_device_with_encryption(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device, with encryption."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TEMP_HUMI_ENCRYPTED_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "get_encryption_key"

    with patch("homeassistant.components.bthome.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "231d39c1d7cc1ab1aee224cd096db932"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TEST DEVICE 80A5"
    assert result2["data"] == {"bindkey": "231d39c1d7cc1ab1aee224cd096db932"}
    assert result2["result"].unique_id == "54:48:E6:8F:80:A5"


async def test_async_step_bluetooth_valid_device_encryption_wrong_key(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device, with encryption and invalid key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TEMP_HUMI_ENCRYPTED_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "get_encryption_key"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key"
    assert result2["errors"]["bindkey"] == "decryption_failed"

    # Test can finish flow
    with patch("homeassistant.components.bthome.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "231d39c1d7cc1ab1aee224cd096db932"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TEST DEVICE 80A5"
    assert result2["data"] == {"bindkey": "231d39c1d7cc1ab1aee224cd096db932"}
    assert result2["result"].unique_id == "54:48:E6:8F:80:A5"


async def test_async_step_bluetooth_valid_device_encryption_wrong_key_length(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device, with encryption and wrong key length."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TEMP_HUMI_ENCRYPTED_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "get_encryption_key"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "aa"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key"
    assert result2["errors"]["bindkey"] == "expected_32_characters"

    # Test can finish flow
    with patch("homeassistant.components.bthome.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "231d39c1d7cc1ab1aee224cd096db932"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TEST DEVICE 80A5"
    assert result2["data"] == {"bindkey": "231d39c1d7cc1ab1aee224cd096db932"}
    assert result2["result"].unique_id == "54:48:E6:8F:80:A5"


async def test_async_step_bluetooth_not_supported(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth not supported."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=NOT_BTHOME_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_async_step_user_no_devices_found(hass: HomeAssistant) -> None:
    """Test setup from service info cache with no devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_no_devices_found_2(hass: HomeAssistant) -> None:
    """Test setup from service info cache with no devices found.

    This variant tests with a non-BTHome device known to us.
    """
    with patch(
        "homeassistant.components.bthome.config_flow.async_discovered_service_info",
        return_value=[NOT_BTHOME_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"


async def test_async_step_user_with_found_devices(hass: HomeAssistant) -> None:
    """Test setup from service info cache with devices found."""
    with patch(
        "homeassistant.components.bthome.config_flow.async_discovered_service_info",
        return_value=[PRST_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    with patch("homeassistant.components.bthome.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "54:48:E6:8F:80:A5"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "b-parasite 80A5"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "54:48:E6:8F:80:A5"


async def test_async_step_user_with_found_devices_encryption(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found, with encryption."""
    with patch(
        "homeassistant.components.bthome.config_flow.async_discovered_service_info",
        return_value=[TEMP_HUMI_ENCRYPTED_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "54:48:E6:8F:80:A5"},
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "get_encryption_key"

    with patch("homeassistant.components.bthome.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "231d39c1d7cc1ab1aee224cd096db932"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TEST DEVICE 80A5"
    assert result2["data"] == {"bindkey": "231d39c1d7cc1ab1aee224cd096db932"}
    assert result2["result"].unique_id == "54:48:E6:8F:80:A5"


async def test_async_step_user_with_found_devices_encryption_wrong_key(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found, with encryption and wrong key."""
    # Get a list of devices
    with patch(
        "homeassistant.components.bthome.config_flow.async_discovered_service_info",
        return_value=[TEMP_HUMI_ENCRYPTED_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Pick a device
    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "54:48:E6:8F:80:A5"},
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "get_encryption_key"

    # Try an incorrect key
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key"
    assert result2["errors"]["bindkey"] == "decryption_failed"

    # Check can still finish flow
    with patch("homeassistant.components.bthome.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "231d39c1d7cc1ab1aee224cd096db932"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TEST DEVICE 80A5"
    assert result2["data"] == {"bindkey": "231d39c1d7cc1ab1aee224cd096db932"}
    assert result2["result"].unique_id == "54:48:E6:8F:80:A5"


async def test_async_step_user_with_found_devices_encryption_wrong_key_length(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found, with encryption and wrong key length."""
    # Get a list of devices
    with patch(
        "homeassistant.components.bthome.config_flow.async_discovered_service_info",
        return_value=[TEMP_HUMI_ENCRYPTED_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select a single device
    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "54:48:E6:8F:80:A5"},
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "get_encryption_key"

    # Try an incorrect key
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "aa"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key"
    assert result2["errors"]["bindkey"] == "expected_32_characters"

    # Check can still finish flow
    with patch("homeassistant.components.bthome.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "231d39c1d7cc1ab1aee224cd096db932"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TEST DEVICE 80A5"
    assert result2["data"] == {"bindkey": "231d39c1d7cc1ab1aee224cd096db932"}
    assert result2["result"].unique_id == "54:48:E6:8F:80:A5"


async def test_async_step_user_device_added_between_steps(hass: HomeAssistant) -> None:
    """Test the device gets added via another flow between steps."""
    with patch(
        "homeassistant.components.bthome.config_flow.async_discovered_service_info",
        return_value=[TEMP_HUMI_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.bthome.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "A4:C1:38:8D:18:B2"},
        )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_async_step_user_with_found_devices_already_setup(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="A4:C1:38:8D:18:B2",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bthome.config_flow.async_discovered_service_info",
        return_value=[TEMP_HUMI_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_bluetooth_devices_already_setup(hass: HomeAssistant) -> None:
    """Test we can't start a flow if there is already a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:48:E6:8F:80:A5",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=PRST_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_already_in_progress(hass: HomeAssistant) -> None:
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=PRST_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=PRST_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_async_step_user_takes_precedence_over_discovery(
    hass: HomeAssistant,
) -> None:
    """Test manual setup takes precedence over discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=PRST_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "homeassistant.components.bthome.config_flow.async_discovered_service_info",
        return_value=[PRST_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM

    with patch("homeassistant.components.bthome.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "54:48:E6:8F:80:A5"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "b-parasite 80A5"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "54:48:E6:8F:80:A5"

    # Verify the original one was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)


async def test_async_step_reauth(hass: HomeAssistant) -> None:
    """Test reauth with a key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:48:E6:8F:80:A5",
    )
    entry.add_to_hass(hass)
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    saved_callback(TEMP_HUMI_ENCRYPTED_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    results = hass.config_entries.flow.async_progress()
    assert len(results) == 1
    result = results[0]

    assert result["step_id"] == "get_encryption_key"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "231d39c1d7cc1ab1aee224cd096db932"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_async_step_reauth_wrong_key(hass: HomeAssistant) -> None:
    """Test reauth with a bad key, and that we can recover."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:48:E6:8F:80:A5",
    )
    entry.add_to_hass(hass)
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    saved_callback(TEMP_HUMI_ENCRYPTED_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    results = hass.config_entries.flow.async_progress()
    assert len(results) == 1
    result = results[0]

    assert result["step_id"] == "get_encryption_key"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "5b51a7c91cde6707c9ef18dada143a58"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key"
    assert result2["errors"]["bindkey"] == "decryption_failed"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "231d39c1d7cc1ab1aee224cd096db932"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_async_step_reauth_abort_early(hass: HomeAssistant) -> None:
    """Test we can abort the reauth if there is no encryption.

    (This can't currently happen in practice).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:48:E6:8F:80:A5",
    )
    entry.add_to_hass(hass)

    device = DeviceData()

    result = await entry.start_reauth_flow(hass, data={"device": device})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
