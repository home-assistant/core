"""Tests for the Remember The Milk integration."""

import json
from unittest.mock import mock_open, patch

import pytest

from homeassistant.components import remember_the_milk as rtm
from homeassistant.core import HomeAssistant

from .const import JSON_STRING, PROFILE, TOKEN


def test_set_get_delete_token(hass: HomeAssistant) -> None:
    """Test set, get and delete token."""
    open_mock = mock_open()
    with patch(
        "homeassistant.components.remember_the_milk.storage.Path.open", open_mock
    ):
        config = rtm.RememberTheMilkConfiguration(hass)
        assert open_mock.return_value.write.call_count == 0
        assert config.get_token(PROFILE) is None
        assert open_mock.return_value.write.call_count == 0
        config.set_token(PROFILE, TOKEN)
        assert open_mock.return_value.write.call_count == 1
        assert open_mock.return_value.write.call_args[0][0] == json.dumps(
            {
                "myprofile": {
                    "id_map": {},
                    "token": "mytoken",
                }
            }
        )
        assert config.get_token(PROFILE) == TOKEN
        assert open_mock.return_value.write.call_count == 1
        config.delete_token(PROFILE)
        assert open_mock.return_value.write.call_count == 2
        assert open_mock.return_value.write.call_args[0][0] == json.dumps({})
        assert config.get_token(PROFILE) is None
        assert open_mock.return_value.write.call_count == 2


def test_config_load(hass: HomeAssistant) -> None:
    """Test loading from the file."""
    with (
        patch(
            "homeassistant.components.remember_the_milk.storage.Path.open",
            mock_open(read_data=JSON_STRING),
        ),
    ):
        config = rtm.RememberTheMilkConfiguration(hass)

    rtm_id = config.get_rtm_id(PROFILE, "123")
    assert rtm_id is not None
    assert rtm_id == ("1", "2", "3")


@pytest.mark.parametrize(
    "side_effect", [FileNotFoundError("Missing file"), OSError("IO error")]
)
def test_config_load_file_error(hass: HomeAssistant, side_effect: Exception) -> None:
    """Test loading with file error."""
    config = rtm.RememberTheMilkConfiguration(hass)
    with (
        patch(
            "homeassistant.components.remember_the_milk.storage.Path.open",
            side_effect=side_effect,
        ),
    ):
        config = rtm.RememberTheMilkConfiguration(hass)

    # The config should be empty and we should not have any errors
    # when trying to access it.
    rtm_id = config.get_rtm_id(PROFILE, "123")
    assert rtm_id is None


def test_config_load_invalid_data(hass: HomeAssistant) -> None:
    """Test loading invalid data."""
    config = rtm.RememberTheMilkConfiguration(hass)
    with (
        patch(
            "homeassistant.components.remember_the_milk.storage.Path.open",
            mock_open(read_data="random characters"),
        ),
    ):
        config = rtm.RememberTheMilkConfiguration(hass)

    # The config should be empty and we should not have any errors
    # when trying to access it.
    rtm_id = config.get_rtm_id(PROFILE, "123")
    assert rtm_id is None


def test_config_set_delete_id(hass: HomeAssistant) -> None:
    """Test setting and deleting an id from the config."""
    hass_id = "123"
    list_id = "1"
    timeseries_id = "2"
    rtm_id = "3"
    open_mock = mock_open()
    config = rtm.RememberTheMilkConfiguration(hass)
    with patch(
        "homeassistant.components.remember_the_milk.storage.Path.open", open_mock
    ):
        config = rtm.RememberTheMilkConfiguration(hass)
        assert open_mock.return_value.write.call_count == 0
        assert config.get_rtm_id(PROFILE, hass_id) is None
        assert open_mock.return_value.write.call_count == 0
        config.set_rtm_id(PROFILE, hass_id, list_id, timeseries_id, rtm_id)
        assert (list_id, timeseries_id, rtm_id) == config.get_rtm_id(PROFILE, hass_id)
        assert open_mock.return_value.write.call_count == 1
        assert open_mock.return_value.write.call_args[0][0] == json.dumps(
            {
                "myprofile": {
                    "id_map": {
                        "123": {"list_id": "1", "timeseries_id": "2", "task_id": "3"}
                    }
                }
            }
        )
        config.delete_rtm_id(PROFILE, hass_id)
        assert config.get_rtm_id(PROFILE, hass_id) is None
        assert open_mock.return_value.write.call_count == 2
        assert open_mock.return_value.write.call_args[0][0] == json.dumps(
            {
                "myprofile": {
                    "id_map": {},
                }
            }
        )
