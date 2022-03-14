"""Constants for LG webOS Smart TV tests."""
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.webostv.const import LIVE_TV_APP_ID

FAKE_UUID = "some-fake-uuid"
TV_NAME = "fake_webos"
ENTITY_ID = f"{MP_DOMAIN}.{TV_NAME}"
HOST = "1.2.3.4"
CLIENT_KEY = "some-secret"
MOCK_CLIENT_KEYS = {HOST: CLIENT_KEY}
MOCK_JSON = '{"1.2.3.4": "some-secret"}'

CHANNEL_1 = {
    "channelNumber": "1",
    "channelName": "Channel 1",
    "channelId": "ch1id",
}
CHANNEL_2 = {
    "channelNumber": "20",
    "channelName": "Channel Name 2",
    "channelId": "ch2id",
}

MOCK_APPS = {
    LIVE_TV_APP_ID: {
        "title": "Live TV",
        "id": LIVE_TV_APP_ID,
        "largeIcon": "large-icon",
        "icon": "icon",
    },
}

MOCK_INPUTS = {
    "in1": {"label": "Input01", "id": "in1", "appId": "app0"},
    "in2": {"label": "Input02", "id": "in2", "appId": "app1"},
}
