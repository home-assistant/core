"""The tests for the androidtv remote platform."""

from typing import Any
from unittest.mock import call, patch

from androidtv.constants import KEYS
import pytest

from homeassistant.components.androidtv.const import (
    CONF_TURN_OFF_COMMAND,
    CONF_TURN_ON_COMMAND,
)
from homeassistant.components.remote import (
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import patchers
from .common import (
    CONFIG_ANDROID_DEFAULT,
    CONFIG_FIRETV_DEFAULT,
    SHELL_RESPONSE_OFF,
    SHELL_RESPONSE_STANDBY,
    setup_mock_entry,
)

from tests.common import MockConfigEntry


def _setup(config: dict[str, Any]) -> tuple[str, str, MockConfigEntry]:
    """Prepare mock entry for the media player tests."""
    return setup_mock_entry(config, REMOTE_DOMAIN)


async def _test_service(
    hass: HomeAssistant,
    entity_id,
    ha_service_name,
    androidtv_method,
    additional_service_data=None,
    expected_call_args=None,
) -> None:
    """Test generic Android media player entity service."""
    if expected_call_args is None:
        expected_call_args = [None]

    service_data = {ATTR_ENTITY_ID: entity_id}
    if additional_service_data:
        service_data.update(additional_service_data)

    androidtv_patch = (
        "androidtv.androidtv_async.AndroidTVAsync"
        if "android" in entity_id
        else "firetv.firetv_async.FireTVAsync"
    )
    with patch(f"androidtv.{androidtv_patch}.{androidtv_method}") as api_call:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            ha_service_name,
            service_data=service_data,
            blocking=True,
        )
        assert api_call.called
        assert api_call.call_count == len(expected_call_args)
        expected_calls = [call(s) if s else call() for s in expected_call_args]
        assert api_call.call_args_list == expected_calls


@pytest.mark.parametrize("config", [CONFIG_ANDROID_DEFAULT, CONFIG_FIRETV_DEFAULT])
async def test_services_remote(hass: HomeAssistant, config) -> None:
    """Test services for remote entity."""
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with patchers.patch_connect(True)[patch_key]:
        with patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with (
            patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key],
            patchers.PATCH_SCREENCAP,
        ):
            await _test_service(hass, entity_id, SERVICE_TURN_OFF, "turn_off")
            await _test_service(hass, entity_id, SERVICE_TURN_ON, "turn_on")
            await _test_service(
                hass,
                entity_id,
                SERVICE_SEND_COMMAND,
                "adb_shell",
                {ATTR_COMMAND: ["BACK", "test"], ATTR_NUM_REPEATS: 2},
                [
                    f"input keyevent {KEYS['BACK']}",
                    "test",
                    f"input keyevent {KEYS['BACK']}",
                    "test",
                ],
            )


@pytest.mark.parametrize("config", [CONFIG_ANDROID_DEFAULT, CONFIG_FIRETV_DEFAULT])
async def test_services_remote_custom(hass: HomeAssistant, config) -> None:
    """Test services with custom options for remote entity."""
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_TURN_OFF_COMMAND: "test off",
            CONF_TURN_ON_COMMAND: "test on",
        },
    )

    with patchers.patch_connect(True)[patch_key]:
        with patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with (
            patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key],
            patchers.PATCH_SCREENCAP,
        ):
            await _test_service(
                hass, entity_id, SERVICE_TURN_OFF, "adb_shell", None, ["test off"]
            )
            await _test_service(
                hass, entity_id, SERVICE_TURN_ON, "adb_shell", None, ["test on"]
            )


async def test_remote_unicode_decode_error(hass: HomeAssistant) -> None:
    """Test sending a command via the send_command remote service that raises a UnicodeDecodeError exception."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)
    response = b"test response"

    with patchers.patch_connect(True)[patch_key]:
        with patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with patch(
            "androidtv.basetv.basetv_async.BaseTVAsync.adb_shell",
            side_effect=UnicodeDecodeError("utf-8", response, 0, len(response), "TEST"),
        ) as api_call:
            try:
                await hass.services.async_call(
                    REMOTE_DOMAIN,
                    SERVICE_SEND_COMMAND,
                    service_data={ATTR_ENTITY_ID: entity_id, ATTR_COMMAND: "BACK"},
                    blocking=True,
                )
                pytest.fail("Exception not raised")
            except ServiceValidationError:
                assert api_call.call_count == 1
