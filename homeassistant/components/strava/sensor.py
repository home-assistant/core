import logging

from datetime import timedelta
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_ATHLETE = 'athlete'
CONF_ACTIVITY = 'last_activity'
CONF_CLUB = 'club'
CONF_GEAR = 'gear'
CONF_BIKE = 'bike'
CONF_SHOE = 'shoe'
CONF_STATS = 'stats'
CONF_FIELDS = 'fields'

DOMAIN = 'strava'

ICON = 'mdi:strava'

SCAN_INTERVAL = timedelta(minutes=1)

DEPENDENCIES = ['strava']

ICON_MAPPING_FIELDS = {
    'member_count': 'mdi:account-multiple',
    'follower_count': 'mdi:account-multiple',
    'distance': 'mdi:map-marker-distance',
    'moving_time': 'mdi:timer',
    'elapsed_time': 'mdi:timer',
    'start_latlng': 'mdi:map-marker',
    'end_latlng': 'mdi:map-marker',
    'total_elevation_gain': 'mdi:elevation-rise',
    'elev_high': 'mdi:elevation-rise',
    'elev_low': 'mdi:elevation-decline',
    'start_date': 'mdi:calendar-range',
    'start_date_local': 'mdi:calendar-range',
    'achievement_count': 'mdi:trophy',
    'kudos_count': 'mdi:account-heart',
    'comment_count': 'mdi:comment',
    'athlete_count': 'mdi:account-multiple',
    'friend_count': 'mdi:account-multiple',
    'photo_count': 'mdi:image',
    'total_photo_count': 'mdi:image',
    'average_speed': 'mdi:speedometer',
    'max_speed': 'mdi:speedometer',
    'kilojoules': 'mdi:fire',
    'average_watts': 'mdi:power-plug',
    'device_watts': 'mdi:power-plug',
    'max_watts': 'mdi:power-plug',
    'weighted_average_watts': 'mdi:power-plug',
    'max_heartrate': 'mdi:heart',
    'average_heartrate': 'mdi:heart',
    'calories': 'mdi:fire',
    'suffer_score': 'mdi:hospital'
}

ICON_MAPPING_ACTIVITY_TYPES = {
    'AlpineSki': None,
    'BackcountrySki': None,
    'Canoeing': None,
    'Crossfit': None,
    'EBikeRide': None,
    'Elliptical': None,
    'Golf': 'mdi:golf',
    'Handcycle': None,
    'Hike': None,
    'IceSkate': 'mdi:skate',
    'InlineSkate': 'mdi:roller-skate',
    'Kayaking': None,
    'Kitesurf': None,
    'NordicSki': None,
    'Ride': 'bike',
    'RockClimbing': None,
    'RollerSki': None,
    'Rowing': 'mdi:rowing',
    'Run': 'mdi:run',
    'Sail': 'mdi:ferry',
    'Skateboard': None,
    'Snowboard': None,
    'Snowshoe': None,
    'Soccer': 'mdi:soccer',
    'StairStepper': 'mdi:stairs',
    'StandUpPaddling': None,
    'Surfing': None,
    'Swim': 'swim',
    'Velomobile': None,
    'VirtualRide': None,
    'VirtualRun': None,
    'Walk': 'mdi:walk',
    'WeightTraining': None,
    'Wheelchair': None,
    'Windsurf': None,
    'Workout': None,
    'Yoga': None
}


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):

    data = hass.data.get(DOMAIN)

    athlete_id = config.get(CONF_ATHLETE)
    gear_id = config.get(CONF_GEAR)
    club_id = config.get(CONF_CLUB)
    bike_id = config.get(CONF_BIKE)
    shoe_id = config.get(CONF_SHOE)

    fields = config.get(CONF_FIELDS) or []
    stats = config.get(CONF_STATS) or []
    activity = config.get(CONF_ACTIVITY) or []

    sensors = []

    if bike_id:
        gear_id = 'b{}'.format(bike_id)
    elif shoe_id:
        gear_id = 'g{}'.format(shoe_id)

    if athlete_id:
        if athlete_id == 'me':
            athlete_id = None

        for field in stats:
            sensor = StravaAthleteStatsSensor(data, athlete_id, field)
            sensors.append(sensor)

        for field in activity:
            sensor = StravaLastActivitySensor(data, athlete_id, field)
            sensors.append(sensor)

        for field in fields:
            sensor = StravaAthleteDetailsSensor(data, athlete_id, field)
            sensors.append(sensor)

    elif gear_id:
        for field in fields:
            sensor = StravaGearSensor(data, gear_id, field)
            sensors.append(sensor)

    elif club_id:
        for field in fields:
            sensor = StravaClubSensor(data, club_id, field)
            sensors.append(sensor)

    add_entities(sensors, True)


class StravaSensor(Entity):

    def __init__(self, field):
        self._state = None

        if '.' in field:
            comps = field.split('.')

            self._field = comps[0]
            self._subfield = comps[1]
        else:
            self._field = field
            self._subfield = None

    @property
    def state(self):
        """Return the state of the sensor."""
        from stravalib.model import ActivityTotals
        from units.quantity import Quantity

        attr = getattr(self._state, self._field, None)
        if isinstance(attr, ActivityTotals):
            attr = getattr(attr, self._subfield, None)

        if isinstance(attr, Quantity):
            return attr.num
        else:
            return attr

    @property
    def unit_of_measurement(self):
        from stravalib.model import ActivityTotals
        from units.quantity import Quantity

        attr = getattr(self._state, self._field, None)
        if isinstance(attr, ActivityTotals):
            attr = getattr(attr, self._subfield, None)

        if isinstance(attr, Quantity):
            return str(attr.unit)
        else:
            return None

    @property
    def icon(self):
        if self._field and self._field in ICON_MAPPING_FIELDS:
            return ICON_MAPPING_FIELDS[self._field]
        elif self._subfield and self._subfield in ICON_MAPPING_FIELDS:
            return ICON_MAPPING_FIELDS[self._subfield]
        else:
            return ICON

    @property
    def available(self):
        return self._state is not None


class StravaLastActivitySensor(StravaSensor):
    """Representation of an Activity Sensor."""

    def __init__(self, data, athlete_id, field):
        super().__init__(field)

        self._data = data.get_athlete(athlete_id)

    async def async_update(self):
        try:
            await self._data.update(self.hass)
            self._state = self._data.last_activity
        except:
            self._state = None

    @property
    def name(self):
        if self.available:
            name = self._data.last_activity.name
        else:
            name = 'Last Activity'

        field = self._field.replace('_', ' ').title()

        return '{}: {}'.format(name, field)

    @property
    def unique_id(self):
        field = self._field
        if self._subfield:
            field += '_' + self._subfield

        return 'strava_athlete_{}_last_activity_{}'.format(
            self._data.id, field)


class StravaAthleteDetailsSensor(StravaSensor):
    """Representation of an Athlete Sensor."""

    def __init__(self, data, athlete_id, field):
        super().__init__(field)

        self._data = data.get_athlete(athlete_id)

    async def async_update(self):
        try:
            await self._data.update(self.hass)
            self._state = self._data.details
        except:
            self._state = None

    @property
    def name(self):
        if self.available:
            name = '{} {}'.format(
                self._data.details.firstname,
                self._data.details.lastname)
        elif self._data.id:
            name = 'Athlete {}'.format(self._data.id)
        else:
            name = 'Athlete'

        field = self._field.replace('_', ' ').title()
        name += ': {}'.format(field)

        if self._subfield:
            subfield = self._subfield.replace('_', ' ').title()
            name += ' {}'.format(subfield)

        return name

    @property
    def entity_picture(self):
        if self.available:
            return self._data.details.profile

    @property
    def unique_id(self):
        field = self._field
        if self._subfield:
            field += '_' + self._subfield

        return 'strava_athelete_{}_details_{}'.format(
            self._data.id, field)


class StravaAthleteStatsSensor(StravaSensor):

    def __init__(self, data, athlete_id, field):
        super().__init__(field)

        self._data = data.get_athlete(athlete_id)

    async def async_update(self):
        try:
            await self._data.update(self.hass)
            self._state = self._data.stats
        except:
            self._state = None

    @property
    def name(self):
        if self._data.details:
            name = '{} {}'.format(
                self._data.details.firstname,
                self._data.details.lastname)
        elif self._data.id:
            name = 'Athlete {}'.format(self._data.id)
        else:
            name = 'Athlete'

        field = self._field.replace('_', ' ').title()
        name += ': {}'.format(field)

        if self._subfield:
            subfield = self._subfield.replace('_', ' ').title()
            name += ' {}'.format(subfield)

        return name

    @property
    def entity_picture(self):
        if self._data.details:
            return self._data.details.profile

    @property
    def unique_id(self):
        field = self._field
        if self._subfield:
            field += '_' + self._subfield

        return 'strava_athelete_{}_stats_{}'.format(
            self._data.id, field)


class StravaClubSensor(StravaSensor):

    def __init__(self, data, club_id, field):
        super().__init__(field)

        self._data = data.get_club(club_id)

    async def async_update(self):
        try:
            await self._data.update(self.hass)
            self._state = self._data.club
        except:
            self._state = None

    @property
    def name(self):
        if self.available:
            name = self._state.name
        else:
            name = 'Club {}'.format(self._data.id)

        field = self._field.replace('_', ' ').title()
        name += ': {}'.format(field)

        if self._subfield:
            subfield = self._subfield.replace('_', ' ').title()
            name += ' {}'.format(subfield)

        return name

    @property
    def entity_picture(self):
        if self.available:
            return self._state.profile_medium

    @property
    def unique_id(self):
        return 'strava_club_{}_{}'.format(
            self._data.id, self._field)


class StravaGearSensor(StravaSensor):

    def __init__(self, data, gear_id, field):
        super().__init__(field)

        self._data = data.get_gear(gear_id)

    async def async_update(self):
        try:
            await self._data.update(self.hass)
            self._state = self._data.gear
        except:
            self._state = None

    @property
    def name(self):
        if self.available:
            name = self._state.name
        else:
            name = 'Gear {}'.format(self._data.id)

        field = self._field.replace('_', ' ').title()
        name += ': {}'.format(field)

        if self._subfield:
            subfield = self._subfield.replace('_', ' ').title()
            name += ' {}'.format(subfield)

        return name

    @property
    def unique_id(self):
        return 'strava_gear_{}_{}'.format(
            self._data.id, self._field)
