import stateData from './state_data';

function getTime(minutesAgo) {
  const ts = new Date(Date.now() - (minutesAgo * 60 * 1000));
  return ts.toISOString();
}

// prefill with entities we do not want to track
const seen = {
  'a.demo_mode': true,
  'configurator.philips_hue': true,
  'group.default_view': true,
  'group.rooms_view': true,
  'group.rooms': true,
  'zone.school': true,
  'zone.work': true,
  'zone.home': true,
  'group.general': true,
  'camera.roundabout': true,
  'script.water_lawn': true,
  'scene.romantic': true,
  'scene.good_morning': true,
  'group.cooking': true,
};
const history = [];

function randomTimeAdjustment(diff) {
  return Math.random() * diff - (diff / 2);
}

const maxTime = 1440;

function addEntity(state, deltas) {
  seen[state.entity_id] = true;
  let changes;
  if (typeof deltas[0] === 'string') {
    changes = deltas.map(state_ => ({ state: state_ }));
  } else {
    changes = deltas;
  }

  const timeDiff = (900 / changes.length);

  history.push(changes.map(
    (change, index) => {
      let attributes;
      if (!change.attributes && !state.attributes) {
        attributes = {};
      } else if (!change.attributes) {
        attributes = state.attributes;
      } else if (!state.attributes) {
        attributes = change.attributes;
      } else {
        attributes = Object.assign({}, state.attributes, change.attributes);
      }

      const time = index === 0 ? getTime(maxTime) : getTime(maxTime - index * timeDiff +
                                                    randomTimeAdjustment(timeDiff));

      return {
        attributes,
        entity_id: state.entity_id,
        state: change.state || state.state,
        last_changed: time,
        last_updated: time,
      };
    }));
}

addEntity(
  {
    entity_id: 'sensor.humidity',
    attributes: {
      unit_of_measurement: '%',
    },
  }, ['45', '49', '52', '49', '52', '49', '45', '42']
);

addEntity(
  {
    entity_id: 'sensor.temperature',
    attributes: {
      unit_of_measurement: '\u00b0C',
    },
  }, ['23', '27', '25', '23', '24']
);

addEntity(
  {
    entity_id: 'thermostat.nest',
    attributes: {
      unit_of_measurement: '\u00b0C',
    },
  }, [
    {
      state: '23',
      attributes: {
        current_temperature: 20,
        temperature: 23,
      },
    },
    {
      state: '23',
      attributes: {
        current_temperature: 22,
        temperature: 23,
      },
    },
    {
      state: '20',
      attributes: {
        current_temperature: 21,
        temperature: 20,
      },
    },
    {
      state: '20',
      attributes: {
        current_temperature: 20,
        temperature: 20,
      },
    },
    {
      state: '20',
      attributes: {
        current_temperature: 19,
        temperature: 20,
      },
    },
  ]
);

addEntity(
  {
    entity_id: 'media_player.living_room',
    attributes: {
      friendly_name: 'Chromecast',
    },
  }, ['Plex', 'idle', 'YouTube', 'Netflix', 'idle', 'Plex']
);

addEntity(
  {
    entity_id: 'group.all_devices',
  }, ['home', 'not_home', 'home']
);

addEntity(
  {
    entity_id: 'device_tracker.paulus',
  }, ['home', 'not_home', 'work', 'not_home']
);

addEntity(
  {
    entity_id: 'device_tracker.anne_therese',
  }, ['home', 'not_home', 'home', 'not_home', 'school']
);

addEntity(
  {
    entity_id: 'garage_door.garage_door',
  }, ['open', 'closed', 'open']
);

addEntity(
  {
    entity_id: 'alarm_control_panel.home',
  }, ['disarmed', 'pending', 'armed_home', 'pending', 'disarmed', 'pending', 'armed_home']
);

addEntity(
  {
    entity_id: 'lock.kitchen_door',
  }, ['unlocked', 'locked', 'unlocked', 'locked']
);

addEntity(
  {
    entity_id: 'light.tv_back_light',
  }, ['on', 'off', 'on', 'off']
);

addEntity(
  {
    entity_id: 'light.ceiling',
  }, ['on', 'off', 'on']
);

addEntity(
  {
    entity_id: 'light.table_lamp',
  }, ['on', 'off', 'on']
);

addEntity(
  {
    entity_id: 'switch.ac',
  }, ['on', 'off', 'on']
);

addEntity(
  {
    entity_id: 'group.bedroom',
  }, ['on', 'off', 'on', 'off']
);

addEntity(
  {
    entity_id: 'group.living_room',
  }, ['on', 'off', 'on']
);

addEntity(
  {
    entity_id: 'switch.decorative_lights',
  }, ['on', 'off', 'on', 'off']
);

addEntity(
  {
    entity_id: 'light.bed_light',
  }, ['on', 'off', 'on', 'off']
);

addEntity(
  {
    entity_id: 'rollershutter.bedroom_window',
  }, ['open', 'closed', 'open', 'closed']
);

addEntity(
  {
    entity_id: 'input_select.cook_today',
  }, ['Anne Therese', 'Paulus']
);

addEntity(
  {
    entity_id: 'input_boolean.notify_cook',
  }, ['off', 'on']
);

if (__DEV__) {
  for (let i = 0; i < stateData.length; i++) {
    const entity = stateData[i];
    if (!(entity.entity_id in seen)) {
      /* eslint-disable no-console */
      console.warn(`Missing history for ${entity.entity_id}`);
      /* eslint-enable no-console */
    }
  }
}

export default history;
