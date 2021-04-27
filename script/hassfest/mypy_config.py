"""Generate mypy config."""
from __future__ import annotations

import configparser
import io
from typing import Final

from .model import Config, Integration

# Modules which have type hints which known to be broken.
# If you are an author of component listed here, please fix these errors and
# remove your component from this list to enable type checks.
# Do your best to not add anything new here.
IGNORED_MODULES: Final[list[str]] = [
    "homeassistant.components.adguard.*",
    "homeassistant.components.aemet.*",
    "homeassistant.components.airly.*",
    "homeassistant.components.alarmdecoder.*",
    "homeassistant.components.alexa.*",
    "homeassistant.components.almond.*",
    "homeassistant.components.amcrest.*",
    "homeassistant.components.analytics.*",
    "homeassistant.components.asuswrt.*",
    "homeassistant.components.atag.*",
    "homeassistant.components.aurora.*",
    "homeassistant.components.awair.*",
    "homeassistant.components.axis.*",
    "homeassistant.components.azure_devops.*",
    "homeassistant.components.azure_event_hub.*",
    "homeassistant.components.blueprint.*",
    "homeassistant.components.bluetooth_tracker.*",
    "homeassistant.components.bmw_connected_drive.*",
    "homeassistant.components.bsblan.*",
    "homeassistant.components.camera.*",
    "homeassistant.components.canary.*",
    "homeassistant.components.cast.*",
    "homeassistant.components.cert_expiry.*",
    "homeassistant.components.climacell.*",
    "homeassistant.components.climate.*",
    "homeassistant.components.cloud.*",
    "homeassistant.components.cloudflare.*",
    "homeassistant.components.config.*",
    "homeassistant.components.control4.*",
    "homeassistant.components.conversation.*",
    "homeassistant.components.deconz.*",
    "homeassistant.components.demo.*",
    "homeassistant.components.denonavr.*",
    "homeassistant.components.device_tracker.*",
    "homeassistant.components.devolo_home_control.*",
    "homeassistant.components.dhcp.*",
    "homeassistant.components.directv.*",
    "homeassistant.components.doorbird.*",
    "homeassistant.components.dsmr.*",
    "homeassistant.components.dynalite.*",
    "homeassistant.components.eafm.*",
    "homeassistant.components.edl21.*",
    "homeassistant.components.elgato.*",
    "homeassistant.components.elkm1.*",
    "homeassistant.components.emonitor.*",
    "homeassistant.components.enphase_envoy.*",
    "homeassistant.components.entur_public_transport.*",
    "homeassistant.components.esphome.*",
    "homeassistant.components.evohome.*",
    "homeassistant.components.fan.*",
    "homeassistant.components.filter.*",
    "homeassistant.components.fints.*",
    "homeassistant.components.fireservicerota.*",
    "homeassistant.components.firmata.*",
    "homeassistant.components.fitbit.*",
    "homeassistant.components.flo.*",
    "homeassistant.components.fortios.*",
    "homeassistant.components.foscam.*",
    "homeassistant.components.freebox.*",
    "homeassistant.components.fritz.*",
    "homeassistant.components.fritzbox.*",
    "homeassistant.components.garmin_connect.*",
    "homeassistant.components.geniushub.*",
    "homeassistant.components.gios.*",
    "homeassistant.components.glances.*",
    "homeassistant.components.gogogate2.*",
    "homeassistant.components.google_assistant.*",
    "homeassistant.components.google_maps.*",
    "homeassistant.components.google_pubsub.*",
    "homeassistant.components.gpmdp.*",
    "homeassistant.components.gree.*",
    "homeassistant.components.growatt_server.*",
    "homeassistant.components.gtfs.*",
    "homeassistant.components.guardian.*",
    "homeassistant.components.habitica.*",
    "homeassistant.components.harmony.*",
    "homeassistant.components.hassio.*",
    "homeassistant.components.hdmi_cec.*",
    "homeassistant.components.here_travel_time.*",
    "homeassistant.components.hisense_aehw4a1.*",
    "homeassistant.components.home_connect.*",
    "homeassistant.components.home_plus_control.*",
    "homeassistant.components.homeassistant.*",
    "homeassistant.components.homekit.*",
    "homeassistant.components.homekit_controller.*",
    "homeassistant.components.homematicip_cloud.*",
    "homeassistant.components.honeywell.*",
    "homeassistant.components.hue.*",
    "homeassistant.components.huisbaasje.*",
    "homeassistant.components.humidifier.*",
    "homeassistant.components.iaqualink.*",
    "homeassistant.components.icloud.*",
    "homeassistant.components.ihc.*",
    "homeassistant.components.image.*",
    "homeassistant.components.incomfort.*",
    "homeassistant.components.influxdb.*",
    "homeassistant.components.input_boolean.*",
    "homeassistant.components.input_datetime.*",
    "homeassistant.components.input_number.*",
    "homeassistant.components.insteon.*",
    "homeassistant.components.ipp.*",
    "homeassistant.components.isy994.*",
    "homeassistant.components.izone.*",
    "homeassistant.components.kaiterra.*",
    "homeassistant.components.keenetic_ndms2.*",
    "homeassistant.components.kodi.*",
    "homeassistant.components.konnected.*",
    "homeassistant.components.kostal_plenticore.*",
    "homeassistant.components.kulersky.*",
    "homeassistant.components.lifx.*",
    "homeassistant.components.litejet.*",
    "homeassistant.components.litterrobot.*",
    "homeassistant.components.lovelace.*",
    "homeassistant.components.luftdaten.*",
    "homeassistant.components.lutron_caseta.*",
    "homeassistant.components.lyric.*",
    "homeassistant.components.marytts.*",
    "homeassistant.components.media_source.*",
    "homeassistant.components.melcloud.*",
    "homeassistant.components.meteo_france.*",
    "homeassistant.components.metoffice.*",
    "homeassistant.components.minecraft_server.*",
    "homeassistant.components.mobile_app.*",
    "homeassistant.components.modbus.*",
    "homeassistant.components.motion_blinds.*",
    "homeassistant.components.motioneye.*",
    "homeassistant.components.mqtt.*",
    "homeassistant.components.mullvad.*",
    "homeassistant.components.mysensors.*",
    "homeassistant.components.n26.*",
    "homeassistant.components.neato.*",
    "homeassistant.components.ness_alarm.*",
    "homeassistant.components.nest.*",
    "homeassistant.components.netatmo.*",
    "homeassistant.components.netio.*",
    "homeassistant.components.nightscout.*",
    "homeassistant.components.nilu.*",
    "homeassistant.components.nmap_tracker.*",
    "homeassistant.components.norway_air.*",
    "homeassistant.components.notion.*",
    "homeassistant.components.nsw_fuel_station.*",
    "homeassistant.components.nuki.*",
    "homeassistant.components.nws.*",
    "homeassistant.components.nzbget.*",
    "homeassistant.components.omnilogic.*",
    "homeassistant.components.onboarding.*",
    "homeassistant.components.ondilo_ico.*",
    "homeassistant.components.onewire.*",
    "homeassistant.components.onvif.*",
    "homeassistant.components.ovo_energy.*",
    "homeassistant.components.ozw.*",
    "homeassistant.components.panasonic_viera.*",
    "homeassistant.components.philips_js.*",
    "homeassistant.components.pilight.*",
    "homeassistant.components.ping.*",
    "homeassistant.components.pioneer.*",
    "homeassistant.components.plaato.*",
    "homeassistant.components.plex.*",
    "homeassistant.components.plugwise.*",
    "homeassistant.components.plum_lightpad.*",
    "homeassistant.components.point.*",
    "homeassistant.components.profiler.*",
    "homeassistant.components.proxmoxve.*",
    "homeassistant.components.rachio.*",
    "homeassistant.components.rainmachine.*",
    "homeassistant.components.recollect_waste.*",
    "homeassistant.components.recorder.*",
    "homeassistant.components.reddit.*",
    "homeassistant.components.ring.*",
    "homeassistant.components.rituals_perfume_genie.*",
    "homeassistant.components.roku.*",
    "homeassistant.components.rpi_power.*",
    "homeassistant.components.ruckus_unleashed.*",
    "homeassistant.components.sabnzbd.*",
    "homeassistant.components.screenlogic.*",
    "homeassistant.components.script.*",
    "homeassistant.components.search.*",
    "homeassistant.components.sense.*",
    "homeassistant.components.sentry.*",
    "homeassistant.components.sesame.*",
    "homeassistant.components.sharkiq.*",
    "homeassistant.components.shell_command.*",
    "homeassistant.components.shelly.*",
    "homeassistant.components.sma.*",
    "homeassistant.components.smart_meter_texas.*",
    "homeassistant.components.smartthings.*",
    "homeassistant.components.smarttub.*",
    "homeassistant.components.smarty.*",
    "homeassistant.components.smhi.*",
    "homeassistant.components.solaredge.*",
    "homeassistant.components.solarlog.*",
    "homeassistant.components.somfy.*",
    "homeassistant.components.somfy_mylink.*",
    "homeassistant.components.sonarr.*",
    "homeassistant.components.songpal.*",
    "homeassistant.components.sonos.*",
    "homeassistant.components.spotify.*",
    "homeassistant.components.stream.*",
    "homeassistant.components.stt.*",
    "homeassistant.components.surepetcare.*",
    "homeassistant.components.switchbot.*",
    "homeassistant.components.switcher_kis.*",
    "homeassistant.components.synology_dsm.*",
    "homeassistant.components.synology_srm.*",
    "homeassistant.components.system_health.*",
    "homeassistant.components.system_log.*",
    "homeassistant.components.tado.*",
    "homeassistant.components.tasmota.*",
    "homeassistant.components.tcp.*",
    "homeassistant.components.telegram_bot.*",
    "homeassistant.components.template.*",
    "homeassistant.components.tesla.*",
    "homeassistant.components.timer.*",
    "homeassistant.components.todoist.*",
    "homeassistant.components.toon.*",
    "homeassistant.components.tplink.*",
    "homeassistant.components.trace.*",
    "homeassistant.components.tradfri.*",
    "homeassistant.components.tuya.*",
    "homeassistant.components.twentemilieu.*",
    "homeassistant.components.unifi.*",
    "homeassistant.components.upcloud.*",
    "homeassistant.components.updater.*",
    "homeassistant.components.upnp.*",
    "homeassistant.components.velbus.*",
    "homeassistant.components.vera.*",
    "homeassistant.components.verisure.*",
    "homeassistant.components.vizio.*",
    "homeassistant.components.volumio.*",
    "homeassistant.components.webostv.*",
    "homeassistant.components.wemo.*",
    "homeassistant.components.wink.*",
    "homeassistant.components.withings.*",
    "homeassistant.components.wled.*",
    "homeassistant.components.wunderground.*",
    "homeassistant.components.xbox.*",
    "homeassistant.components.xiaomi_aqara.*",
    "homeassistant.components.xiaomi_miio.*",
    "homeassistant.components.yamaha.*",
    "homeassistant.components.yeelight.*",
    "homeassistant.components.zerproc.*",
    "homeassistant.components.zha.*",
    "homeassistant.components.zwave.*",
]

HEADER: Final = """
# Automatically generated by hassfest.
#
# To update, run python3 -m script.hassfest

""".lstrip()

GENERAL_SETTINGS: Final[dict[str, str]] = {
    "python_version": "3.8",
    "show_error_codes": "true",
    "follow_imports": "silent",
    "ignore_missing_imports": "true",
    "warn_incomplete_stub": "true",
    "warn_redundant_casts": "true",
    "warn_unused_configs": "true",
}

# This is basically the list of checks which is enabled for "strict=true".
# But "strict=true" is applied globally, so we need to list all checks manually.
STRICT_SETTINGS: Final[list[str]] = [
    "check_untyped_defs",
    "disallow_incomplete_defs",
    "disallow_subclassing_any",
    "disallow_untyped_calls",
    "disallow_untyped_decorators",
    "disallow_untyped_defs",
    "no_implicit_optional",
    "strict_equality",
    "warn_return_any",
    "warn_unreachable",
    "warn_unused_ignores",
    # TODO: turn these on, address issues
    # "disallow_any_generics",
    # "no_implicit_reexport",
]


def generate_and_validate(config: Config) -> str:
    """Validate and generate mypy config."""

    config_path = config.root / ".strict-typing"

    with config_path.open() as fp:
        lines = fp.readlines()

    # Filter empty and commented lines.
    strict_modules: list[str] = [
        line.strip()
        for line in lines
        if line.strip() != "" and not line.startswith("#")
    ]

    ignored_modules_set: set[str] = set(IGNORED_MODULES)
    for module in strict_modules:
        if (
            not module.startswith("homeassistant.components.")
            and module != "homeassistant.components"
        ):
            config.add_error(
                "mypy_config", f"Only components should be added: {module}"
            )
        if module in ignored_modules_set:
            config.add_error("mypy_config", f"Module '{module}' is in ignored list")

    mypy_config = configparser.ConfigParser()

    general_section = "mypy"
    mypy_config.add_section(general_section)
    for key, value in GENERAL_SETTINGS.items():
        mypy_config.set(general_section, key, value)
    for key in STRICT_SETTINGS:
        mypy_config.set(general_section, key, "true")

    # By default strict checks are disabled for components.
    components_section = "mypy-homeassistant.components.*"
    mypy_config.add_section(components_section)
    for key in STRICT_SETTINGS:
        mypy_config.set(components_section, key, "false")

    strict_section = "mypy-" + ",".join(strict_modules)
    mypy_config.add_section(strict_section)
    for key in STRICT_SETTINGS:
        mypy_config.set(strict_section, key, "true")

    ignored_section = "mypy-" + ",".join(IGNORED_MODULES)
    mypy_config.add_section(ignored_section)
    mypy_config.set(ignored_section, "ignore_errors", "true")

    with io.StringIO() as fp:
        mypy_config.write(fp)
        fp.seek(0)
        return HEADER + fp.read().strip()


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate mypy config."""
    config_path = config.root / "mypy.ini"
    config.cache["mypy_config"] = content = generate_and_validate(config)

    with open(str(config_path)) as fp:
        if fp.read().strip() != content:
            config.add_error(
                "mypy_config",
                "File mypy.ini is not up to date. Run python3 -m script.hassfest",
                fixable=True,
            )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate mypy config."""
    config_path = config.root / "mypy.ini"
    with open(str(config_path), "w") as fp:
        fp.write(f"{config.cache['mypy_config']}\n")
