"""
Support for the Unitymedia Horizon HD Recorder.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/media_player.horizon/
"""

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA, MEDIA_TYPE_CHANNEL,
    SUPPORT_NEXT_TRACK, SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_PAUSE,
    SUPPORT_PLAY, SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE)
from homeassistant.const import (CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF,
                                 STATE_PAUSED, STATE_PLAYING)
import homeassistant.helpers.config_validation as cv
import homeassistant.util as util

REQUIREMENTS = ['einder==0.3.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Horizon"
DEFAULT_PORT = 5900

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

SUPPORT_UPC_HORIZON = SUPPORT_NEXT_TRACK | SUPPORT_PAUSE | SUPPORT_PLAY | \
    SUPPORT_PLAY_MEDIA | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_SELECT_SOURCE | SUPPORT_TURN_ON | \
    SUPPORT_TURN_OFF

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Horizon platform."""
    from einder import Client, keys
    from einder.exceptions import AuthenticationError

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    port = config.get(CONF_PORT)

    _LOGGER.info("Connecting to Horizon at %s", host)

    try:
        client = Client(host, port=port)
    except AuthenticationError:
        _LOGGER.error("Authenticating to Horizon at %s failed!", host)
        return False

    _LOGGER.info("Connection to Horizon at %s established", host)

    add_devices([HorizonDevice(client, name, keys)], True)


class HorizonDevice(MediaPlayerDevice):
    """Representation of a Horizon HD Recorder."""

    def __init__(self, client, name, keys):
        """Initialize the remote."""
        self._name = name
        self._client = client
        self._state = False
        self._keys = keys
        self._source_list = {1: 'Das Erste HD', 2: 'ZDF HD', 3: 'RTL HD',
                             4: 'Sat.1 HD', 5: 'ProSieben HD', 6: 'VOX HD',
                             7: 'kabel eins HD', 8: 'RTL2 HD', 9: '3Sat HD',
                             10: 'arte HD', 11: 'ServusTV HD',
                             20: 'WDR Köln HD', 31: 'hr-fernsehen HD',
                             32: 'BR Fernsehen Süd HD',
                             34: 'MDR Thüringen HD',
                             37: 'NDR Niedersachsen HD', 42: 'rbb Berlin HD',
                             43: 'SR Fernsehen HD', 46: 'SWR BW HD',
                             50: 'Baden TV HD*', 51: 'Baden TV Süd HD*',
                             56: 'L-TV HD*', 58: 'Regio TV AA HD*',
                             59: 'Regio TV BB HD*', 61: 'Regio TV LB HD*',
                             62: 'Regio TV Ost HD*', 63: 'Regio TV S HD*',
                             64: 'Regio TV Süd HD*',
                             65: 'Regio TV Ulm HD*', 66: 'Regio TV West HD*',
                             69: 'RNF HD*', 102: 'QVC HD',
                             103: 'HSE24 HD', 104: 'Sonnenklar TV HD',
                             105: '1-2-3.TV HD', 106: 'Juwelo TV HD',
                             109: 'QVC2 HD', 110: 'HSE24 Extra HD',
                             111: 'QVC Style HD', 120: 'DMAX HD',
                             122: 'TLC HD',
                             126: 'Bibel TV HD', 140: 'NatGeo HD',
                             141: 'Spiegel TV Wissen HD',
                             142: 'Discovery Channel HD', 143: 'History HD',
                             144: 'PLANET HD', 145: 'NAT GEO WILD HD',
                             146: 'Animal Planet HD', 384: 'NRWision*',
                             391: 'Offener Kanal*', 394: 'Rhein-Main TV*',
                             366: 'Regio TV West*', 367: 'RIK Reutlingen*',
                             368: 'RIK tv*', 369: 'RNF*', 370: 'RTF 1*',
                             371: 'SF1*', 372: 'SF2*', 373: 'TeleBasel*',
                             382: 'Lokalprogramm*',
                             399: 'Unitymedia Schnupperkanal',
                             400: 'Unitymedia Videothek',
                             401: 'Unitymedia Infokanal',
                             402: 'QVC', 403: 'HSE24', 404: 'sonnenklar.TV',
                             405: '1-2-3.tv', 406: 'Juwelo',
                             407: 'Channel21', 408: 'SparhandyTV', 409: 'QVC2',
                             410: 'HSE24 EXTRA', 411: 'QVC Style',
                             412: 'HSE24 TREND', 414: 'Astro TV', 420: 'DMAX',
                             421: 'ZDFinfo', 422: 'TLC',
                             423: 'kabel eins Doku', 424: 'N24 Doku',
                             425: 'ARD alpha', 426: 'Bibel TV',
                             427: 'DIE NEUE ZEIT TV', 429: 'K-TV',
                             430: 'SonLife', 432: 'God.TV', 433: 'HEALTH TV',
                             434: 'Hope Channel', 435: 'Welt der Wunder',
                             440: 'NATIONAL GEOGRAPHIC (1',
                             441: 'SPIEGEL TV Wissen',
                             442: 'Discovery Channel', 443: 'HISTORY',
                             444: 'PLANET',
                             445: 'NatGeo Wild', 600: 'TRT Türk',
                             601: 'Habertürk', 604: 'ATV Avrupa',
                             606: 'CNN Türk',
                             663: 'DM SAT', 607: 'EURO STAR', 608: 'Kanal 7',
                             609: 'NTV Avrupa', 610: 'Power Türk TV',
                             611: 'SHOW TURK', 612: 'TV 8', 623: 'KAZAKH TV',
                             672: 'TV Crne Gore Sat', 673: 'Hayat TV',
                             625: 'OstWest', 626: 'Telebom / Tele Dom',
                             677: 'Klan Kosova', 633: 'Mediaset',
                             634: 'Rai Uno', 635: 'Rai Due',
                             637: 'Rai News 24', 638: 'Rai Storia',
                             682: 'TV5MONDE Europe', 683: 'TF 1*',
                             685: 'France 2', 644: 'itvn', 687: 'France 3',
                             645: 'TV Polonia', 646: 'TV Silesia',
                             649: 'Record Internacional', 651: '24Horas',
                             652: 'RTPi', 653: 'TVE Internacional',
                             700: 'Sky 1 HD', 701: 'Sky Atlantic HD',
                             702: 'Fox HD (S)', 703: 'TNT Serie HD (S)',
                             704: 'NatGeo HD (S)', 705: 'Nat Geo Wild HD',
                             706: 'Discovery HD (S)', 709: 'Sky 1',
                             710: 'Sky Krimi', 711: 'Sky Atlantic',
                             712: 'Fox Serie (S)', 713: 'TNT Serie (S)',
                             714: 'RTL Crime (S)', 715: 'Syfy (S)',
                             716: '13th Street (S)', 717: 'RTL Passion (S)',
                             718: 'Beate-Uhse.TV', 719: 'Heimatkanal',
                             720: 'Goldstar TV', 724: 'Classica',
                             766: 'Sky Sport 1', 725: 'Discovery Channel (S)',
                             726: 'National Geographic (S)',
                             731: 'NatGeo Wild', 772: 'Sky Sport 7',
                             732: 'Sky Cinema Action HD',
                             733: 'Disney Cinemagic HD', 734: 'Sky Cinema',
                             735: 'Sky Cinema +1', 736: 'Sky Cinema +24',
                             737: 'Sky Cinema Hits',
                             738: 'Sky Cinema Action',
                             739: 'Sky Cinema Family',
                             740: 'Sky Cinema Comedy',
                             741: 'Sky Cinema Emotion',
                             742: 'Sky Cinema Nostalgie',
                             743: 'Disney Cinemagic',
                             801: '1LIVE', 802: '1LIVE diggi', 803: 'WDRcosmo',
                             804: 'KIRAKA', 805: 'WDR 2 Rheinland',
                             806: 'WDR 3', 807: 'WDR 4', 808: 'WDR 5',
                             809: 'WDR Event', 810: 'DASDING',
                             811: 'WDR Rhein und Ruhr', 812: 'SWRinfo',
                             813: 'SWR1 BW', 814: 'SWR1 RP', 815: 'SWR2',
                             816: 'SWR3', 817: 'SWR4 BW', 818: 'SWR4 RP',
                             819: 'hr1', 820: 'hr2', 821: 'hr3',
                             822: 'hr4', 823: 'hr-iNFO', 824: 'YOU FM',
                             825: 'B5 aktuell', 826: 'B5 plus',
                             827: 'Bayern 1', 828: 'Bayern 2', 829: 'BAYERN 3',
                             830: 'BAYERN plus', 833: 'BR-KLASSIK',
                             890: 'Radio Seefunk*',
                             966: 'BBC World Service (2)', 834: 'MDR JUMP',
                             835: 'MDR KLASSIK',
                             836: 'MDR KULTUR', 837: 'MDR S-ANHALT',
                             839: 'MDR SPUTNIK', 840: 'MDR THÜRINGEN',
                             841: 'MDR1 SACHSEN', 842: 'NDR 1 Nieders.',
                             843: 'NDR 1 Radio MV', 844: 'NDR 2',
                             845: 'NDR 90', 846: 'NDR Blue', 847: 'NDR Info',
                             848: 'NDR Info Spez.', 849: 'NDR Kultur',
                             850: 'NDR Plus'}

    @property
    def name(self):
        """Return the name of the remote."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def keys(self):
        """Return the predefined keys."""
        return self._keys

    @property
    def source_list(self):
        """List of available (german) TV channels (names only)."""
        return [self._source_list[c] for c in sorted(self._source_list.keys())]

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_UPC_HORIZON

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Update State using the media server running on the Horizon."""
        from einder.exceptions import AuthenticationError

        if self._client.con is None:
            try:
                self._client.connect()
                self._client.authorize()
            except AuthenticationError:
                _LOGGER.error("Re-authenticating to Horizon failed!")
                return False

        if self._client.is_powered_on():
            self._state = STATE_PLAYING
        else:
            self._state = STATE_OFF

    def turn_on(self):
        """Turn the device on."""
        self._client.power_on()

    def turn_off(self):
        """Turn the device off."""
        self._client.power_off()

    def media_previous_track(self):
        """Channel down."""
        self._client.send_key(self._keys.CHAN_DOWN)
        self._state = STATE_PLAYING

    def media_next_track(self):
        """Channel up."""
        self._client.send_key(self._keys.CHAN_UP)
        self._state = STATE_PLAYING

    def play_media(self, media_type, media_id, **kwargs):
        """Play media / switch to channel."""
        if MEDIA_TYPE_CHANNEL == media_type and isinstance(int(media_id), int):
            self._client.select_channel(media_id)
            self._state = STATE_PLAYING
        else:
            _LOGGER.error("Invalid type %s or channel %d",
                          media_type, media_id)
            _LOGGER.error("Only %s is supported", MEDIA_TYPE_CHANNEL)

    def media_play(self):
        """Send play command."""
        self._client.send_key(self._keys.PAUSE)
        self._state = STATE_PLAYING

    def media_pause(self):
        """Send pause command."""
        self._client.send_key(self._keys.PAUSE)
        self._state = STATE_PAUSED

    def media_play_pause(self):
        """Send play/pause command."""
        self._client.send_key(self._keys.PAUSE)
        if self._state == STATE_PAUSED:
            self._state = STATE_PLAYING
        else:
            self._state = STATE_PAUSED

    def select_source(self, source):
        """Select a channel."""
        if str(source).isdigit():
            digits = str(source)
        else:
            digits = [str(k) for k, v
                      in self._source_list.items()
                      if v == source]

        if digits is not None:
            self._client.select_channel("".join(digits))
            self._state = STATE_PLAYING
