"""Tests for the Remember The Milk integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import mock_open, patch

import pytest

from homeassistant.components.remember_the_milk import (
    DOMAIN,
    RememberTheMilkConfiguration,
)
from homeassistant.core import HomeAssistant

from .const import JSON_STRING, PROFILE, STORED_DATA, TOKEN

from tests.common import async_fire_time_changed

pytestmark = pytest.mark.parametrize("new_storage_exists", [True, False])


@pytest.fixture(autouse=True)
def mock_path_exists(new_storage_exists: bool) -> Generator[None]:
    """Mock path exists."""
    with patch(
        "homeassistant.components.remember_the_milk.storage.Path.exists",
        return_value=new_storage_exists,
    ):
        yield


@pytest.fixture(autouse=True)
def mock_delay_save() -> Generator[None]:
    """Mock delay save."""
    with patch(
        "homeassistant.components.remember_the_milk.storage.STORE_DELAY_SAVE", 0
    ):
        yield


async def test_set_get_delete_token(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test set, get and delete token."""
    open_mock = mock_open()
    config = RememberTheMilkConfiguration(hass)
    with patch(
        "homeassistant.components.remember_the_milk.storage.Path.open", open_mock
    ):
        await config.setup()
        assert config.get_token(PROFILE) is None
        config.set_token(PROFILE, TOKEN)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass_storage[DOMAIN]["data"] == {
            "myprofile": {
                "id_map": {},
                "token": "mytoken",
            }
        }
        assert config.get_token(PROFILE) == TOKEN
        config.delete_token(PROFILE)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass_storage[DOMAIN]["data"] == {}
        assert config.get_token(PROFILE) is None


async def test_config_load(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test loading from the file."""
    hass_storage[DOMAIN] = {
        "data": STORED_DATA,
        "key": DOMAIN,
        "version": 1,
        "minor_version": 1,
    }
    config = RememberTheMilkConfiguration(hass)
    with (
        patch(
            "homeassistant.components.remember_the_milk.storage.Path.open",
            mock_open(read_data=JSON_STRING),
        ),
    ):
        await config.setup()

    rtm_id = config.get_rtm_id(PROFILE, "123")
    assert rtm_id is not None
    assert rtm_id == ("1", "2", "3")


@pytest.mark.parametrize(
    "side_effect", [FileNotFoundError("Missing file"), OSError("IO error")]
)
async def test_config_load_file_error(
    hass: HomeAssistant, side_effect: Exception
) -> None:
    """Test loading with file error."""
    config = RememberTheMilkConfiguration(hass)
    with (
        patch(
            "homeassistant.components.remember_the_milk.storage.Path.open",
            side_effect=side_effect,
        ),
    ):
        await config.setup()

    # The config should be empty and we should not have any errors
    # when trying to access it.
    rtm_id = config.get_rtm_id(PROFILE, "123")
    assert rtm_id is None


async def test_config_load_invalid_data(hass: HomeAssistant) -> None:
    """Test loading invalid data."""
    config = RememberTheMilkConfiguration(hass)
    with (
        patch(
            "homeassistant.components.remember_the_milk.storage.Path.open",
            mock_open(read_data="random characters"),
        ),
    ):
        await config.setup()

    # The config should be empty and we should not have any errors
    # when trying to access it.
    rtm_id = config.get_rtm_id(PROFILE, "123")
    assert rtm_id is None


async def test_config_set_delete_id(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test setting and deleting an id from the config."""
    hass_id = "123"
    list_id = "1"
    timeseries_id = "2"
    rtm_id = "3"
    open_mock = mock_open()
    config = RememberTheMilkConfiguration(hass)
    with patch(
        "homeassistant.components.remember_the_milk.storage.Path.open", open_mock
    ):
        await config.setup()
        assert config.get_rtm_id(PROFILE, hass_id) is None
        config.set_rtm_id(PROFILE, hass_id, list_id, timeseries_id, rtm_id)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (list_id, timeseries_id, rtm_id) == config.get_rtm_id(PROFILE, hass_id)
        assert hass_storage[DOMAIN]["data"] == {
            "myprofile": {
                "id_map": {
                    "123": {"list_id": "1", "timeseries_id": "2", "task_id": "3"}
                }
            }
        }
        config.delete_rtm_id(PROFILE, hass_id)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert config.get_rtm_id(PROFILE, hass_id) is None
        assert hass_storage[DOMAIN]["data"] == {
            "myprofile": {
                "id_map": {},
            }
        }
