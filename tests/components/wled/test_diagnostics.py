"""Tests for the diagnostics data provided by the WLED integration."""
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "info": {
            "architecture": "esp8266",
            "arduino_core_version": "2.4.2",
            "brand": "WLED",
            "build_type": "bin",
            "effect_count": 81,
            "filesystem": None,
            "free_heap": 14600,
            "leds": {
                "__type": "<class 'wled.models.Leds'>",
                "repr": (
                    "Leds(cct=False, count=30, fps=None, light_capabilities=None, "
                    "max_power=850, max_segments=10, power=470, rgbw=False, wv=True, "
                    "segment_light_capabilities=None)"
                ),
            },
            "live_ip": "Unknown",
            "live_mode": "Unknown",
            "live": False,
            "mac_address": "aabbccddeeff",
            "name": "WLED RGB Light",
            "pallet_count": 50,
            "product": "DIY light",
            "udp_port": 21324,
            "uptime": 32,
            "version_id": 1909122,
            "version": "0.8.5",
            "version_latest_beta": "0.13.0b1",
            "version_latest_stable": "0.12.0",
            "websocket": None,
            "wifi": "**REDACTED**",
        },
        "state": {
            "brightness": 127,
            "nightlight": {
                "__type": "<class 'wled.models.Nightlight'>",
                "repr": (
                    "Nightlight(duration=60, fade=True, on=False,"
                    " mode=<NightlightMode.FADE: 1>, target_brightness=0)"
                ),
            },
            "on": True,
            "playlist": -1,
            "preset": -1,
            "segments": [
                {
                    "__type": "<class 'wled.models.Segment'>",
                    "repr": (
                        "Segment(brightness=127, clones=-1,"
                        " color_primary=(255, 159, 0),"
                        " color_secondary=(0, 0, 0),"
                        " color_tertiary=(0, 0, 0),"
                        " effect=Effect(effect_id=0, name='Solid'),"
                        " intensity=128, length=20, on=True,"
                        " palette=Palette(name='Default', palette_id=0),"
                        " reverse=False, segment_id=0, selected=True,"
                        " speed=32, start=0, stop=19)"
                    ),
                },
                {
                    "__type": "<class 'wled.models.Segment'>",
                    "repr": (
                        "Segment(brightness=127, clones=-1,"
                        " color_primary=(0, 255, 123),"
                        " color_secondary=(0, 0, 0),"
                        " color_tertiary=(0, 0, 0),"
                        " effect=Effect(effect_id=1, name='Blink'),"
                        " intensity=64, length=10, on=True,"
                        " palette=Palette(name='Random Cycle', palette_id=1),"
                        " reverse=True, segment_id=1, selected=True,"
                        " speed=16, start=20, stop=30)"
                    ),
                },
            ],
            "sync": {
                "__type": "<class 'wled.models.Sync'>",
                "repr": "Sync(receive=True, send=False)",
            },
            "transition": 7,
            "lor": 0,
        },
        "effects": {
            "27": "Android",
            "68": "BPM",
            "1": "Blink",
            "26": "Blink Rainbow",
            "2": "Breathe",
            "13": "Chase",
            "28": "Chase",
            "31": "Chase Flash",
            "32": "Chase Flash Rnd",
            "14": "Chase Rainbow",
            "30": "Chase Rainbow",
            "29": "Chase Random",
            "52": "Circus",
            "34": "Colorful",
            "8": "Colorloop",
            "74": "Colortwinkle",
            "67": "Colorwaves",
            "21": "Dark Sparkle",
            "18": "Dissolve",
            "19": "Dissolve Rnd",
            "11": "Dual Scan",
            "60": "Dual Scanner",
            "7": "Dynamic",
            "12": "Fade",
            "69": "Fill Noise",
            "66": "Fire 2012",
            "45": "Fire Flicker",
            "42": "Fireworks",
            "46": "Gradient",
            "53": "Halloween",
            "58": "ICU",
            "49": "In In",
            "48": "In Out",
            "64": "Juggle",
            "75": "Lake",
            "41": "Lighthouse",
            "57": "Lightning",
            "47": "Loading",
            "25": "Mega Strobe",
            "44": "Merry Christmas",
            "76": "Meteor",
            "59": "Multi Comet",
            "70": "Noise 1",
            "71": "Noise 2",
            "72": "Noise 3",
            "73": "Noise 4",
            "62": "Oscillate",
            "51": "Out In",
            "50": "Out Out",
            "65": "Palette",
            "63": "Pride 2015",
            "78": "Railway",
            "43": "Rain",
            "9": "Rainbow",
            "33": "Rainbow Runner",
            "5": "Random Colors",
            "38": "Red & Blue",
            "79": "Ripple",
            "15": "Running",
            "37": "Running 2",
            "16": "Saw",
            "10": "Scan",
            "40": "Scanner",
            "77": "Smooth Meteor",
            "0": "Solid",
            "20": "Sparkle",
            "22": "Sparkle+",
            "39": "Stream",
            "61": "Stream 2",
            "23": "Strobe",
            "24": "Strobe Rainbow",
            "6": "Sweep",
            "36": "Sweep Random",
            "35": "Traffic Light",
            "54": "Tri Chase",
            "56": "Tri Fade",
            "55": "Tri Wipe",
            "17": "Twinkle",
            "80": "Twinklefox",
            "3": "Wipe",
            "4": "Wipe Random",
        },
        "palettes": {
            "18": "Analogous",
            "46": "April Night",
            "39": "Autumn",
            "3": "Based on Primary",
            "5": "Based on Set",
            "26": "Beach",
            "22": "Beech",
            "15": "Breeze",
            "48": "C9",
            "7": "Cloud",
            "37": "Cyane",
            "0": "Default",
            "24": "Departure",
            "30": "Drywet",
            "35": "Fire",
            "10": "Forest",
            "32": "Grintage",
            "28": "Hult",
            "29": "Hult 64",
            "36": "Icefire",
            "31": "Jul",
            "25": "Landscape",
            "8": "Lava",
            "38": "Light Pink",
            "40": "Magenta",
            "41": "Magred",
            "9": "Ocean",
            "44": "Orange & Teal",
            "47": "Orangery",
            "6": "Party",
            "20": "Pastel",
            "2": "Primary Color",
            "11": "Rainbow",
            "12": "Rainbow Bands",
            "1": "Random Cycle",
            "16": "Red & Blue",
            "33": "Rewhi",
            "14": "Rivendell",
            "49": "Sakura",
            "4": "Set Colors",
            "27": "Sherbet",
            "19": "Splash",
            "13": "Sunset",
            "21": "Sunset 2",
            "34": "Tertiary",
            "45": "Tiamat",
            "23": "Vintage",
            "43": "Yelblu",
            "17": "Yellowout",
            "42": "Yelmag",
        },
        "playlists": {},
        "presets": {},
    }
