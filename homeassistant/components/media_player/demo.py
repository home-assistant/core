"""
homeassistant.components.media_player.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Demo implementation of the media player.
"""
from homeassistant.const import (
    STATE_PLAYING, STATE_PAUSED, STATE_OFF)

from homeassistant.components.media_player import (
    MediaPlayerDevice,
    MEDIA_TYPE_VIDEO, MEDIA_TYPE_MUSIC, MEDIA_TYPE_TVSHOW,
    SUPPORT_PAUSE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_MUTE,
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_NEXT_TRACK, SUPPORT_PLAY_MEDIA)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the cast platform. """
    add_devices([
        DemoYoutubePlayer(
            'Living Room', 'eyU3bRy2x44',
            '♥♥ The Best Fireplace Video (3 hours)'),
        DemoYoutubePlayer('Bedroom', 'kxopViU98Xo', 'Epic sax guy 10 hours'),
        DemoMusicPlayer(), DemoTVShowPlayer(),
    ])


YOUTUBE_COVER_URL_FORMAT = 'https://img.youtube.com/vi/{}/1.jpg'

YOUTUBE_PLAYER_SUPPORT = \
    SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PLAY_MEDIA

MUSIC_PLAYER_SUPPORT = \
    SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF

NETFLIX_PLAYER_SUPPORT = \
    SUPPORT_PAUSE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF


class AbstractDemoPlayer(MediaPlayerDevice):
    """ Base class for demo media players. """
    # We only implement the methods that we support
    # pylint: disable=abstract-method

    def __init__(self, name):
        self._name = name
        self._player_state = STATE_PLAYING
        self._volume_level = 1.0
        self._volume_muted = False

    @property
    def should_poll(self):
        """ We will push an update after each command. """
        return False

    @property
    def name(self):
        """ Name of the media player. """
        return self._name

    @property
    def state(self):
        """ State of the player. """
        return self._player_state

    @property
    def volume_level(self):
        """ Volume level of the media player (0..1). """
        return self._volume_level

    @property
    def is_volume_muted(self):
        """ Boolean if volume is currently muted. """
        return self._volume_muted

    def turn_on(self):
        """ turn the media player on. """
        self._player_state = STATE_PLAYING
        self.update_ha_state()

    def turn_off(self):
        """ turn the media player off. """
        self._player_state = STATE_OFF
        self.update_ha_state()

    def mute_volume(self, mute):
        """ mute the volume. """
        self._volume_muted = mute
        self.update_ha_state()

    def set_volume_level(self, volume):
        """ set volume level, range 0..1. """
        self._volume_level = volume
        self.update_ha_state()

    def media_play(self):
        """ Send play commmand. """
        self._player_state = STATE_PLAYING
        self.update_ha_state()

    def media_pause(self):
        """ Send pause command. """
        self._player_state = STATE_PAUSED
        self.update_ha_state()


class DemoYoutubePlayer(AbstractDemoPlayer):
    """ A Demo media player that only supports YouTube. """
    # We only implement the methods that we support
    # pylint: disable=abstract-method

    def __init__(self, name, youtube_id=None, media_title=None):
        super().__init__(name)
        self.youtube_id = youtube_id
        self._media_title = media_title

    @property
    def media_content_id(self):
        """ Content ID of current playing media. """
        return self.youtube_id

    @property
    def media_content_type(self):
        """ Content type of current playing media. """
        return MEDIA_TYPE_VIDEO

    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        return 360

    @property
    def media_image_url(self):
        """ Image url of current playing media. """
        return YOUTUBE_COVER_URL_FORMAT.format(self.youtube_id)

    @property
    def media_title(self):
        """ Title of current playing media. """
        return self._media_title

    @property
    def app_name(self):
        """ Current running app. """
        return "YouTube"

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        return YOUTUBE_PLAYER_SUPPORT

    def play_media(self, media_type, media_id):
        """ Plays a piece of media. """
        self.youtube_id = media_id
        self.update_ha_state()


class DemoMusicPlayer(AbstractDemoPlayer):
    """ A Demo media player that only supports YouTube. """
    # We only implement the methods that we support
    # pylint: disable=abstract-method

    tracks = [
        ('Technohead', 'I Wanna Be A Hippy (Flamman & Abraxas Radio Mix)'),
        ('Paul Elstak', 'Luv U More'),
        ('Dune', 'Hardcore Vibes'),
        ('Nakatomi', 'Children Of The Night'),
        ('Party Animals',
         'Have You Ever Been Mellow? (Flamman & Abraxas Radio Mix)'),
        ('Rob G.*', 'Ecstasy, You Got What I Need'),
        ('Lipstick', "I'm A Raver"),
        ('4 Tune Fairytales', 'My Little Fantasy (Radio Edit)'),
        ('Prophet', "The Big Boys Don't Cry"),
        ('Lovechild', 'All Out Of Love (DJ Weirdo & Sim Remix)'),
        ('Stingray & Sonic Driver', 'Cold As Ice (El Bruto Remix)'),
        ('Highlander', 'Hold Me Now (Bass-D & King Matthew Remix)'),
        ('Juggernaut', 'Ruffneck Rules Da Artcore Scene (12" Edit)'),
        ('Diss Reaction', 'Jiiieehaaaa '),
        ('Flamman And Abraxas', 'Good To Go (Radio Mix)'),
        ('Critical Mass', 'Dancing Together'),
        ('Charly Lownoise & Mental Theo',
         'Ultimate Sex Track (Bass-D & King Matthew Remix)'),
    ]

    def __init__(self):
        super().__init__('Walkman')
        self._cur_track = 0

    @property
    def media_content_id(self):
        """ Content ID of current playing media. """
        return 'bounzz-1'

    @property
    def media_content_type(self):
        """ Content type of current playing media. """
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        return 213

    @property
    def media_image_url(self):
        """ Image url of current playing media. """
        return 'https://graph.facebook.com/107771475912710/picture'

    @property
    def media_title(self):
        """ Title of current playing media. """
        return self.tracks[self._cur_track][1]

    @property
    def media_artist(self):
        """ Artist of current playing media. (Music track only) """
        return self.tracks[self._cur_track][0]

    @property
    def media_album_name(self):
        """ Album of current playing media. (Music track only) """
        # pylint: disable=no-self-use
        return "Bounzz"

    @property
    def media_track(self):
        """ Track number of current playing media. (Music track only) """
        return self._cur_track + 1

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        support = MUSIC_PLAYER_SUPPORT

        if self._cur_track > 0:
            support |= SUPPORT_PREVIOUS_TRACK

        if self._cur_track < len(self.tracks)-1:
            support |= SUPPORT_NEXT_TRACK

        return support

    def media_previous_track(self):
        """ Send previous track command. """
        if self._cur_track > 0:
            self._cur_track -= 1
            self.update_ha_state()

    def media_next_track(self):
        """ Send next track command. """
        if self._cur_track < len(self.tracks)-1:
            self._cur_track += 1
            self.update_ha_state()


class DemoTVShowPlayer(AbstractDemoPlayer):
    """ A Demo media player that only supports YouTube. """
    # We only implement the methods that we support
    # pylint: disable=abstract-method

    def __init__(self):
        super().__init__('Lounge room')
        self._cur_episode = 1
        self._episode_count = 13

    @property
    def media_content_id(self):
        """ Content ID of current playing media. """
        return 'house-of-cards-1'

    @property
    def media_content_type(self):
        """ Content type of current playing media. """
        return MEDIA_TYPE_TVSHOW

    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        return 3600

    @property
    def media_image_url(self):
        """ Image url of current playing media. """
        return 'https://graph.facebook.com/HouseofCards/picture'

    @property
    def media_title(self):
        """ Title of current playing media. """
        return 'Chapter {}'.format(self._cur_episode)

    @property
    def media_series_title(self):
        """ Series title of current playing media. (TV Show only)"""
        return 'House of Cards'

    @property
    def media_season(self):
        """ Season of current playing media. (TV Show only) """
        return 1

    @property
    def media_episode(self):
        """ Episode of current playing media. (TV Show only) """
        return self._cur_episode

    @property
    def app_name(self):
        """ Current running app. """
        return "Netflix"

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        support = NETFLIX_PLAYER_SUPPORT

        if self._cur_episode > 1:
            support |= SUPPORT_PREVIOUS_TRACK

        if self._cur_episode < self._episode_count:
            support |= SUPPORT_NEXT_TRACK

        return support

    def media_previous_track(self):
        """ Send previous track command. """
        if self._cur_episode > 1:
            self._cur_episode -= 1
            self.update_ha_state()

    def media_next_track(self):
        """ Send next track command. """
        if self._cur_episode < self._episode_count:
            self._cur_episode += 1
            self.update_ha_state()
