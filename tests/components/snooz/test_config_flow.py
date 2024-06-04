"""Test the Snooz config flow."""

from __future__ import annotations

from asyncio import Event, sleep
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.snooz import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    NOT_SNOOZ_SERVICE_INFO,
    SNOOZ_SERVICE_INFO_NOT_PAIRING,
    SNOOZ_SERVICE_INFO_PAIRING,
    TEST_ADDRESS,
    TEST_PAIRING_TOKEN,
    TEST_SNOOZ_DISPLAY_NAME,
)

from tests.common import MockConfigEntry


async def test_async_step_bluetooth_valid_device(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=SNOOZ_SERVICE_INFO_PAIRING,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    await _test_setup_entry(hass, result["flow_id"])


async def test_async_step_bluetooth_waits_to_pair(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a device that's not in pairing mode, but enters pairing mode to complete setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=SNOOZ_SERVICE_INFO_NOT_PAIRING,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    await _test_pairs(hass, result["flow_id"])


async def test_async_step_bluetooth_retries_pairing(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a device that's not in pairing mode, times out waiting, but eventually complete setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=SNOOZ_SERVICE_INFO_NOT_PAIRING,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    retry_id = await _test_pairs_timeout(hass, result["flow_id"])
    await _test_pairs(hass, retry_id)


async def test_async_step_bluetooth_not_snooz(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth not Snooz."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=NOT_SNOOZ_SERVICE_INFO,
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


async def test_async_step_user_with_found_devices(hass: HomeAssistant) -> None:
    """Test setup from service info cache with devices found."""
    with patch(
        "homeassistant.components.snooz.config_flow.async_discovered_service_info",
        return_value=[SNOOZ_SERVICE_INFO_PAIRING],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"]
    # ensure discovered devices are listed as options
    assert result["data_schema"].schema["name"].container == [TEST_SNOOZ_DISPLAY_NAME]
    await _test_setup_entry(
        hass, result["flow_id"], {CONF_NAME: TEST_SNOOZ_DISPLAY_NAME}
    )


async def test_async_step_user_with_found_devices_waits_to_pair(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found that require pairing mode."""
    with patch(
        "homeassistant.components.snooz.config_flow.async_discovered_service_info",
        return_value=[SNOOZ_SERVICE_INFO_NOT_PAIRING],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    await _test_pairs(hass, result["flow_id"], {CONF_NAME: TEST_SNOOZ_DISPLAY_NAME})


async def test_async_step_user_with_found_devices_retries_pairing(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found that require pairing mode, times out, then completes."""
    with patch(
        "homeassistant.components.snooz.config_flow.async_discovered_service_info",
        return_value=[SNOOZ_SERVICE_INFO_NOT_PAIRING],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    user_input = {CONF_NAME: TEST_SNOOZ_DISPLAY_NAME}

    retry_id = await _test_pairs_timeout(hass, result["flow_id"], user_input)
    await _test_pairs(hass, retry_id, user_input)


async def test_async_step_user_device_added_between_steps(hass: HomeAssistant) -> None:
    """Test the device gets added via another flow between steps."""
    with patch(
        "homeassistant.components.snooz.config_flow.async_discovered_service_info",
        return_value=[SNOOZ_SERVICE_INFO_PAIRING],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        data={CONF_NAME: TEST_SNOOZ_DISPLAY_NAME, CONF_TOKEN: TEST_PAIRING_TOKEN},
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.snooz.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NAME: TEST_SNOOZ_DISPLAY_NAME},
        )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_async_step_user_with_found_devices_already_setup(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        data={CONF_NAME: TEST_SNOOZ_DISPLAY_NAME, CONF_TOKEN: TEST_PAIRING_TOKEN},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.snooz.config_flow.async_discovered_service_info",
        return_value=[SNOOZ_SERVICE_INFO_PAIRING],
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
        unique_id=TEST_ADDRESS,
        data={CONF_NAME: TEST_SNOOZ_DISPLAY_NAME, CONF_TOKEN: TEST_PAIRING_TOKEN},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=SNOOZ_SERVICE_INFO_PAIRING,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_already_in_progress(hass: HomeAssistant) -> None:
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=SNOOZ_SERVICE_INFO_PAIRING,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=SNOOZ_SERVICE_INFO_PAIRING,
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
        data=SNOOZ_SERVICE_INFO_PAIRING,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "homeassistant.components.snooz.config_flow.async_discovered_service_info",
        return_value=[SNOOZ_SERVICE_INFO_PAIRING],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM

    await _test_setup_entry(
        hass, result["flow_id"], {CONF_NAME: TEST_SNOOZ_DISPLAY_NAME}
    )

    # Verify the original one was aborted
    assert not hass.config_entries.flow.async_progress()


async def _test_pairs(
    hass: HomeAssistant, flow_id: str, user_input: dict | None = None
) -> None:
    pairing_mode_entered = Event()

    async def _async_process_advertisements(
        _hass, _callback, _matcher, _mode, _timeout
    ):
        await pairing_mode_entered.wait()
        service_info = SNOOZ_SERVICE_INFO_PAIRING
        assert _callback(service_info)
        return service_info

    with patch(
        "homeassistant.components.snooz.config_flow.async_process_advertisements",
        _async_process_advertisements,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input=user_input or {},
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "wait_for_pairing_mode"

        pairing_mode_entered.set()
        await hass.async_block_till_done()

    await _test_setup_entry(hass, result["flow_id"], user_input)


async def _test_pairs_timeout(
    hass: HomeAssistant, flow_id: str, user_input: dict | None = None
) -> str:
    async def _async_process_advertisements(
        _hass, _callback, _matcher, _mode, _timeout
    ):
        """Simulate a timeout waiting for pairing mode."""
        await sleep(0)
        raise TimeoutError

    with patch(
        "homeassistant.components.snooz.config_flow.async_process_advertisements",
        _async_process_advertisements,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input=user_input or {}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "wait_for_pairing_mode"
        await hass.async_block_till_done()

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "pairing_timeout"

    return result2["flow_id"]


async def _test_setup_entry(
    hass: HomeAssistant, flow_id: str, user_input: dict | None = None
) -> None:
    with patch("homeassistant.components.snooz.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input=user_input or {},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ADDRESS: TEST_ADDRESS,
        CONF_TOKEN: TEST_PAIRING_TOKEN,
    }
    assert result["result"].unique_id == TEST_ADDRESS
