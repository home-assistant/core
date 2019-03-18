from datetime import timedelta
from homeassistant.helpers.entity import Entity

CONF_ATHLETE = 'athelete'
CONF_ACTIVITY = 'activity'
CONF_STATS = 'stats'

DOMAIN = 'strava'

ICON = 'mdi:strava'

SCAN_INTERVAL = timedelta(minutes=1)

DEPENDENCIES = ['strava']

ICON_MAPPING_FIELDS = {
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
    'photo_count': 'mdi:image',
    'total_photo_count': 'mdi:image',
    'average_speed': 'mdi:speedometer',
    'max_speed': 'mdi:speedometer',
    'kilojoules': None,
    'average_watts': 'mdi:power-plug',
    'device_watts': 'mdi:power-plug',
    'max_watts': 'mdi:power-plug',
    'weighted_average_watts': 'mdi:power-plug'
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


class StravaSensor(Entity):

    def __init__(self, data, field):
        self._data = data
        self._client = data.client

        if '.' in field:
            comps = field.split('.')

            self._field = comps[0]
            self._subfield = comps[1]
        else:
            self._field = field

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
        """Return the icon."""
        return ICON

    @property
    def available(self):
        return True

class StravaActivitySensor(StravaSensor):
    """Representation of an Activity Sensor."""

    def __init__(self, data, activity_id, field):
        """ Initialize the sensor. """
        super().__init__(data, field)

        self._activity_id = activity_id

    @property
    def name(self):
        """Return the name of the sensor."""

        field = self._field.replace('_', ' ').title()

        return 'Strava Last Activity: {}'.format(field)

    @property
    def unique_id(self):
        return 'strava_last_activity_{}'.format(self._field)

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        self._data.renew_token()

        activities = self._data.client.get_activities(limit=1)

        self._state = next(activities)

    @property
    def icon(self):
        """Return the icon."""
        if self._state and self._state.type in ICON_MAPPING_ACTIVITY_TYPES:
            return ICON_MAPPING_ACTIVITY_TYPES[self._state.type]
        else:
            return super().icon

    @property
    def device_state_attributes(self):
        from units.quantity import Quantity

        fields = ['gear_id', 'external_id', 'upload_id', 'name', 'distance', 'total_elevation_gain', 'elev_high', 'elev_low', 'type', 'start_date', 'start_date_local', 'achievement_count', 'kudos_count', 'comment_count', 'athlete_count', 'photo_count', 'total_photo_count', 'trainer', 'commute', 'manual', 'private', 'flagged', 'workout_type', 'average_speed', 'max_speed', 'has_kudoed', 'kilojoules', 'average_watts', 'device_watts', 'max_watts', 'weighted_average_watts', 'description', 'calories', 'device_name']
        attrs = {
            'activity_id': self._state.id,
            'start_latlng': (self._state.start_latlng.lat, self._state.start_latlng.lon),
            'end_latlng': (self._state.end_latlng.lat, self._state.end_latlng.lon),
            'moving_time': self._state.moving_time.seconds,
            'elapsed_time': self._state.elapsed_time.seconds,
            'timezone': self._state.timezone.zone
        }

        for field in fields:
            val = getattr(self._state, field)

            if isinstance(val, Quantity):
                val = val.num

            if val is not None:
                attrs[field] = val

        return attrs

class StravaAthleteSensor(StravaSensor):
    """Representation of an Athlete Sensor."""

    def __init__(self, data, athlete_id, field):
        """Initialize the sensor."""
        super().__init__(data, field)
        self._athlete_id = athlete_id
        self._athlete = self._client.get_athlete(athlete_id)

    @property
    def name(self):
        """Return the name of the sensor."""

        field = self._field.replace('_', ' ').title()

        name = 'Strava Stats: {}'.format(field)

        if self._subfield:
            subfield = self._subfield.replace('_', ' ').title()
            name += ' {}'.format(subfield)

        return name

    @property
    def device_state_attributes(self):
        from units.quantity import Quantity

        totals = [
            'recent_ride_totals',
            'recent_run_totals',
            'ytd_ride_totals',
            'ytd_run_totals',
            'all_ride_totals',
            'all_run_totals'
        ]

        fields = [
            'achievement_count',
            'count',
            'distance',
            'elapsed_time',
            'elevation_gain',
            'moving_time'
        ]

        attrs = {
            'athlete_id': self._athlete_id,
            'biggest_ride_distance': self._state.biggest_ride_distance.num,
            'biggest_climb_elevation_gain': self._state.biggest_climb_elevation_gain.num,
        }

        for total in totals:
            t = getattr(self._state, total)
            for field in fields:
                val = getattr(t, field)

                if isinstance(val, Quantity):
                    val = val.num

                if isinstance(val, timedelta):
                    val = val.seconds

                if val is not None:
                    attrs['{}.{}'.format(total, field)] = val


        return attrs

    @property
    def entity_picture(self):
        return self._athlete.profile

    @property
    def unique_id(self):
        return 'strava_athelete_{}_stats_{}'.format(self._athlete_id, self._field)

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        self._data.renew_token()

        if self._data.is_authorized:
            self._state = self._client.get_athlete_stats(self._athlete_id)

    @property
    def icon(self):
        """Return the icon."""
        if self._field and self._field in ICON_MAPPING_FIELDS:
            return ICON_MAPPING_FIELDS[self._field]
        elif self._subfield and self._subfield in ICON_MAPPING_FIELDS:
            return ICON_MAPPING_FIELDS[self._subfield]
        else:
            return super().icon


def setup_platform(hass, config, add_entities, discovery_info=None):

    data = hass.data.get(DOMAIN)

    athlete_id = config.get(CONF_ATHLETE)
    stats = config.get(CONF_STATS)
    activity = config.get(CONF_ACTIVITY)

    if data.is_authorized:
        sensors = []

        for field in stats:
            sensor = StravaAthleteSensor(data, athlete_id, field)
            sensors.append(sensor)

        for field in activity:
            sensor = StravaActivitySensor(data, athlete_id, field)
            sensors.append(sensor)

        add_entities(sensors, True)
