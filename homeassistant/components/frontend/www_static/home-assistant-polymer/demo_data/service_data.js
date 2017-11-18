export default [
  {
    domain: 'homeassistant',
    services: {
      stop: { description: '', fields: {} },
      turn_off: { description: '', fields: {} },
      turn_on: { description: '', fields: {} },
    },
  },
  {
    domain: 'light',
    services: {
      turn_off: { description: '', fields: {} },
      turn_on: { description: '', fields: {} },
    },
  },
  {
    domain: 'switch',
    services: {
      turn_off: { description: '', fields: {} },
      turn_on: { description: '', fields: {} },
    },
  },
  {
    domain: 'input_boolean',
    services: {
      turn_off: { description: '', fields: {} },
      turn_on: { description: '', fields: {} },
    },
  },
  {
    domain: 'configurator',
    services: {
      configure: { description: '', fields: {} },
    },
  },
];
