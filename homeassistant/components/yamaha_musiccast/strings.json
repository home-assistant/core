{
  "config": {
    "flow_title": "MusicCast: {name}",
    "step": {
      "user": {
        "description": "Set up MusicCast to integrate with Home Assistant.",
        "data": {
          "host": "[%key:common::config_flow::data::host%]"
        }
      },
      "confirm": {
        "description": "[%key:common::config_flow::description::confirm_setup%]"
      }
    },
    "abort": {
      "already_configured": "[%key:common::config_flow::abort::already_configured_device%]",
      "yxc_control_url_missing": "The control URL is not given in the ssdp description."
    },
    "error": {
      "no_musiccast_device": "This device seems to be no MusicCast Device."
    }
  },
  "entity": {
    "select": {
      "dimmer": {
        "state": {
          "auto": "Auto"
        }
      },
      "zone_sleep": {
        "state": {
          "off": "[%key:common::state::off%]",
          "30_min": "30 Minutes",
          "60_min": "60 Minutes",
          "90_min": "90 Minutes",
          "120_min": "120 Minutes"
        }
      },
      "zone_tone_control_mode": {
        "state": {
          "manual": "Manual",
          "auto": "Auto",
          "bypass": "Bypass"
        }
      },
      "zone_surr_decoder_type": {
        "state": {
          "toggle": "[%key:common::action::toggle%]",
          "auto": "Auto",
          "dolby_pl": "Dolby ProLogic",
          "dolby_pl2x_movie": "Dolby ProLogic 2x Movie",
          "dolby_pl2x_music": "Dolby ProLogic 2x Music",
          "dolby_pl2x_game": "Dolby ProLogic 2x Game",
          "dolby_surround": "Dolby Surround",
          "dts_neural_x": "DTS Neural:X",
          "dts_neo6_cinema": "DTS Neo:6 Cinema",
          "dts_neo6_music": "DTS Neo:6 Music"
        }
      },
      "zone_equalizer_mode": {
        "state": {
          "manual": "Manual",
          "auto": "Auto",
          "bypass": "[%key:component::yamaha_musiccast::entity::select::zone_tone_control_mode::state::bypass%]"
        }
      },
      "zone_link_audio_quality": {
        "state": {
          "compressed": "Compressed",
          "uncompressed": "Uncompressed"
        }
      },
      "zone_link_control": {
        "state": {
          "standard": "Standard",
          "speed": "Speed",
          "stability": "Stability"
        }
      },
      "zone_link_audio_delay": {
        "state": {
          "audio_sync_on": "Audio Synchronization On",
          "audio_sync_off": "Audio Synchronization Off",
          "balanced": "Balanced",
          "lip_sync": "Lip Synchronization",
          "audio_sync": "Audio Synchronization"
        }
      }
    }
  }
}
