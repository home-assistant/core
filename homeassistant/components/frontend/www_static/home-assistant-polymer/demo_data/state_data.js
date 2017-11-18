function getRandomTime() {
  const ts = new Date(new Date().getTime() - (Math.random() * 80 * 60 * 1000));
  return ts.toISOString();
}

const entities = [];

function addEntity(entityId, state, attributes = {}) {
  entities.push({
    state,
    attributes,
    entity_id: entityId,
    last_changed: getRandomTime(),
    last_updated: getRandomTime(),
  });
}

let groupOrder = 0;

function addGroup(objectId, state, entityIds, name, view) {
  groupOrder++;

  const attributes = {
    entity_id: entityIds,
    order: groupOrder,
  };

  if (name) {
    attributes.friendly_name = name;
  }
  if (view) {
    attributes.view = view;
    attributes.hidden = true;
  }
  addEntity(`group.${objectId}`, state, attributes);
}

// ---------------------------------------------------
//    HOME ASSISTANT
// ---------------------------------------------------
addEntity('a.demo_mode', 'enabled');

addEntity('configurator.philips_hue', 'configure', {
  configure_id: '4415244496-1',
  description: 'Press the button on the bridge to register Philips Hue with Home Assistant.',
  description_image: '/demo/images/config_philips_hue.jpg',
  fields: [],
  submit_caption: 'I have pressed the button',
  friendly_name: 'Philips Hue',
});

// ---------------------------------------------------
//    VIEWS
// ---------------------------------------------------

addGroup(
  'default_view', 'on', [
    'a.demo_mode',
    'sensor.humidity',
    'sensor.temperature',
    'device_tracker.paulus',
    'device_tracker.anne_therese',
    'configurator.philips_hue',
    'group.cooking',
    'group.general',
    'group.rooms',
    'camera.living_room',
    'media_player.living_room',
    'scene.romantic',
    'scene.good_morning',
    'script.water_lawn',
  ], 'Main', true);

addGroup(
  'rooms_view', 'on', [
    'group.living_room',
    'group.bedroom',
  ], 'Rooms', true);

addGroup('rooms', 'on', ['group.living_room', 'group.bedroom'], 'Rooms');

// ---------------------------------------------------
//    DEVICE TRACKER + ZONES
// ---------------------------------------------------

addEntity('device_tracker.anne_therese', 'school', {
  entity_picture: 'https://graph.facebook.com/621994601/picture',
  friendly_name: 'Anne Therese',
  latitude: 32.879898,
  longitude: -117.236776,
  gps_accuracy: 250,
  battery: 76,
});

addEntity('device_tracker.paulus', 'not_home', {
  entity_picture: 'https://graph.facebook.com/297400035/picture',
  friendly_name: 'Paulus',
  gps_accuracy: 75,
  latitude: 32.892950,
  longitude: -117.203431,
  battery: 56,
});

addEntity('zone.school', 'zoning', {
  radius: 250,
  latitude: 32.880834,
  longitude: -117.237556,
  icon: 'mdi:library',
  hidden: true,
});

addEntity('zone.work', 'zoning', {
  radius: 250,
  latitude: 32.896844,
  longitude: -117.202204,
  icon: 'mdi:worker',
  hidden: true,
});

addEntity('zone.home', 'zoning', {
  radius: 100,
  latitude: 32.873708,
  longitude: -117.226590,
  icon: 'mdi:home',
  hidden: true,
});

// ---------------------------------------------------
//    GENERAL
// ---------------------------------------------------
addGroup('general', 'on', [
  'alarm_control_panel.home',
  'garage_door.garage_door',
  'lock.kitchen_door',
  'thermostat.nest',
  'camera.living_room',
]);

addEntity('camera.living_room', 'idle', {
  entity_picture: '/demo/webcam.jpg?',
});

addEntity('garage_door.garage_door', 'open', {
  friendly_name: 'Garage Door',
});

addEntity('alarm_control_panel.home', 'armed_home', {
  friendly_name: 'Alarm',
  code_format: '^\\d{4}',
});

addEntity('lock.kitchen_door', 'open', {
  friendly_name: 'Kitchen Door',
});

// ---------------------------------------------------
//    PRESETS
// ---------------------------------------------------

addEntity('script.water_lawn', 'off', {
  friendly_name: 'Water Lawn',
});
addEntity('scene.romantic', 'scening', {
  friendly_name: 'Romantic',
});
// addEntity('scene.good_morning', 'scening', {
//   friendly_name: 'Good Morning',
// });

// ---------------------------------------------------
//    LIVING ROOM
// ---------------------------------------------------

addGroup(
  'living_room', 'on',
  [
    'light.table_lamp',
    'light.ceiling',
    'light.tv_back_light',
    'switch.ac',
    'media_player.living_room',
  ],
  'Living Room'
);

addEntity('light.tv_back_light', 'off', {
  friendly_name: 'TV Back Light',
});
addEntity('light.ceiling', 'on', {
  friendly_name: 'Ceiling Lights',
  brightness: 200,
  rgb_color: [255, 116, 155],
});
addEntity('light.table_lamp', 'on', {
  brightness: 200,
  rgb_color: [150, 212, 94],
  friendly_name: 'Table Lamp',
});
addEntity('switch.ac', 'on', {
  friendly_name: 'AC',
  icon: 'mdi:air-conditioner',
});
addEntity('media_player.living_room', 'playing', {
  entity_picture: '/demo/images/thrones.jpg',
  friendly_name: 'Chromecast',
  supported_features: 509,
  media_content_type: 'tvshow',
  media_title: 'The Dance of Dragons',
  media_series_title: 'Game of Thrones',
  media_season: 5,
  media_episode: '09',
  app_name: 'HBO Now',
});

// ---------------------------------------------------
//    BEDROOM
// ---------------------------------------------------

addGroup(
  'bedroom', 'off',
  [
    'light.bed_light',
    'switch.decorative_lights',
    'rollershutter.bedroom_window',
  ],
  'Bedroom'
);

addEntity('switch.decorative_lights', 'off', {
  friendly_name: 'Decorative Lights',
});
addEntity('light.bed_light', 'off', {
  friendly_name: 'Bed Light',
});
addEntity('rollershutter.bedroom_window', 'closed', {
  friendly_name: 'Window',
  current_position: 0,
});

// ---------------------------------------------------
//    SENSORS
// ---------------------------------------------------

addEntity('sensor.temperature', '15.6', {
  unit_of_measurement: '\u00b0C',
  friendly_name: 'Temperature',
});
addEntity('sensor.humidity', '54', {
  unit_of_measurement: '%',
  friendly_name: 'Humidity',
});

addEntity('thermostat.nest', '23', {
  away_mode: 'off',
  temperature: '21',
  current_temperature: '18',
  unit_of_measurement: '\u00b0C',
  friendly_name: 'Nest',
});

// ---------------------------------------------------
//    COOKING AUTOMATION
// ---------------------------------------------------
addEntity('input_select.cook_today', 'Paulus', {
  options: ['Paulus', 'Anne Therese'],
  icon: 'mdi:panda',
});

addEntity('input_boolean.notify_cook', 'on', {
  icon: 'mdi:alarm',
  friendly_name: 'Notify Cook',
});

addGroup(
  'cooking', 'unknown',
  ['input_select.cook_today', 'input_boolean.notify_cook']
);

export default entities;
