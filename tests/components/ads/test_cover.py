"""Tests for ADS covers."""
from unittest.mock import patch
import pytest

from __future__ import annotations

from typing import Any

import pyads
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_ADS_VAR,
    CONF_ADS_VAR_POSITION,
    DATA_ADS,
    STATE_KEY_POSITION,
    STATE_KEY_STATE,
    AdsEntity,
)

DEFAULT_NAME = "ADS Cover"

CONF_ADS_VAR_SET_POS = "adsvar_set_position"
CONF_ADS_VAR_OPEN = "adsvar_open"
CONF_ADS_VAR_CLOSE = "adsvar_close"
CONF_ADS_VAR_STOP = "adsvar_stop"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_VAR): cv.string,
        vol.Optional(CONF_ADS_VAR_POSITION): cv.string,
        vol.Optional(CONF_ADS_VAR_SET_POS): cv.string,
        vol.Optional(CONF_ADS_VAR_CLOSE): cv.string,
        vol.Optional(CONF_ADS_VAR_OPEN): cv.string,
        vol.Optional(CONF_ADS_VAR_STOP): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)



# def is_closed(self) -> bool | None:
def test_is_closed_ads_var_not_none(self):
    #Caso 1
    self._ads_var = "test.var"

    assert self.is_closed() == self._state_dict[STATE_KEY_STATE]

def test_is_closed_ads_var_position_not_none(self):
    #Caso 2
    self._ads_var = None
    self._ads_var_position = "test.var_pos"

    assert self.is_closed() == self._state_dict[STATE_KEY_POSITION] == 0

def test_is_closed_ads_var_none(self):
    #Caso 3
    self._ads_var = None
    self._ads_var_position = None

    assert self.is_closed() == None



# def stop_cover(self, **kwargs: Any) -> None:
def test_stop_cover_ads_var_stop_not_none(self):
    #caso 1
    self._ads_var_stop = "test.var_stop"

    assert self.stop_cover() == self._ads_hub.read_by_name(self._ads_var_stop, True)



# def set_cover_position(self, **kwargs: Any) -> None:
def test_set_cover_position_ads_var_pos_set_not_none(self):
    #caso 1
    self._ads_var_pos_set = "test.var_pos_set"

    assert self.set_cover_position(position=0) == self._ads_hub.read_by_name(self._ads_var_pos_set, 0)



# def open_cover(self, **kwargs: Any) -> None:
def test_open_cover_ads_var_open_not_none(self):
    #caso 1
    self._ads_var_open = "test.var_open"
    self._ads_var_pos_set = None

    assert self.open_cover() == self._ads_hub.read_by_name(self._ads_var_open, True)

def test_open_cover_ads_var_pos_set_not_none(self):
    #caso 2
    self._ads_var_open = "test.var_open"
    self._ads_var_pos_set = "test.var_pos_set"

    assert self.open_cover() == self.get_cover_position(position)



# def close_cover(self, **kwargs: Any) -> None:
def test_close_cover_ads_var_close_not_none(self):
    #caso 1
    self._ads_var_close = "test.var_close"
    self._ads_var_pos_set = None

    assert self.close_cover() == self._ads_hub.read_by_name(self._ads_var_close, True)

def test_close_cover_ads_var_pos_set_not_none(self):
    #caso 2
    self._ads_var_close = "test.var_close"
    self._ads_var_pos_set = "test.var_pos_set"

    assert self.close_cover() == self.get_cover_position(position)
    


# def available(self) -> bool:
def test_available_ads_var_and_ads_var_position_none(self):
    #caso 1
    self._ads_var = None
    self._ads_var_position = None

    assert self.available() == 

def test_available_ads_var_position_not_none(self):
    #caso 2
    self._ads_var = None
    self._ads_var_position = "test.var_pos"

    assert self.available() == True

def test_available_ads_var_not_none(self):
    #caso 3
    self._ads_var = "test.var"
    self._ads_var_position = None

    assert self.available() == True

def test_available_ads_var_and_ads_var_position_not_none(self):
    #caso 4
    self._ads_var = "test.var"
    self._ads_var_position = "test.var_pos"

    assert self.available() == False
