"""Tests for the Google Assistant integration."""

DEMO_DEVICES = [{
    'id':
    'light.kitchen_lights',
    'name': {
        'name': 'Kitchen Lights'
    },
    'traits': [
        'action.devices.traits.OnOff', 'action.devices.traits.Brightness',
        'action.devices.traits.ColorSpectrum',
        'action.devices.traits.ColorTemperature'
    ],
    'type':
    'action.devices.types.LIGHT',
    'willReportState':
    False
}, {
    'id':
    'switch.ac',
    'name': {
        'name': 'AC'
    },
    'traits': [
        'action.devices.traits.OnOff'
    ],
    'type': 'action.devices.types.SWITCH',
    'willReportState':
    False
}, {
    'id':
    'switch.decorative_lights',
    'name': {
        'name': 'Decorative Lights'
    },
    'traits': [
        'action.devices.traits.OnOff'
    ],
    'type': 'action.devices.types.SWITCH',
    'willReportState':
    False
}, {
    'id':
    'light.ceiling_lights',
    'name': {
        'name': 'Roof Lights',
        'nicknames': ['top lights', 'ceiling lights']
    },
    'traits': [
        'action.devices.traits.OnOff', 'action.devices.traits.Brightness',
        'action.devices.traits.ColorSpectrum',
        'action.devices.traits.ColorTemperature'
    ],
    'type':
    'action.devices.types.LIGHT',
    'willReportState':
    False
}, {
    'id':
    'light.bed_light',
    'name': {
        'name': 'Bed Light'
    },
    'traits': [
        'action.devices.traits.OnOff', 'action.devices.traits.Brightness',
        'action.devices.traits.ColorSpectrum',
        'action.devices.traits.ColorTemperature'
    ],
    'type':
    'action.devices.types.LIGHT',
    'willReportState':
    False
}, {
    'id': 'group.all_lights',
    'name': {
        'name': 'all lights'
    },
    'traits': ['action.devices.traits.OnOff'],
    'type': 'action.devices.types.SWITCH',
    'willReportState': False
}, {
    'id': 'group.all_switches',
    'name': {
        'name': 'all switches'
    },
    'traits': ['action.devices.traits.OnOff'],
    'type': 'action.devices.types.SWITCH',
    'willReportState': False
}, {
    'id':
    'cover.living_room_window',
    'name': {
        'name': 'Living Room Window'
    },
    'traits':
    ['action.devices.traits.OnOff', 'action.devices.traits.Brightness'],
    'type':
    'action.devices.types.SWITCH',
    'willReportState':
    False
}, {
    'id':
    'cover.hall_window',
    'name': {
        'name': 'Hall Window'
    },
    'traits':
    ['action.devices.traits.OnOff', 'action.devices.traits.Brightness'],
    'type':
    'action.devices.types.SWITCH',
    'willReportState':
    False
}, {
    'id': 'cover.garage_door',
    'name': {
        'name': 'Garage Door'
    },
    'traits': ['action.devices.traits.OnOff'],
    'type': 'action.devices.types.SWITCH',
    'willReportState': False
}, {
    'id': 'cover.kitchen_window',
    'name': {
        'name': 'Kitchen Window'
    },
    'traits': ['action.devices.traits.OnOff'],
    'type': 'action.devices.types.SWITCH',
    'willReportState': False
}, {
    'id': 'group.all_covers',
    'name': {
        'name': 'all covers'
    },
    'traits': ['action.devices.traits.OnOff'],
    'type': 'action.devices.types.SWITCH',
    'willReportState': False
}, {
    'id':
    'media_player.bedroom',
    'name': {
        'name': 'Bedroom'
    },
    'traits':
    ['action.devices.traits.OnOff', 'action.devices.traits.Brightness'],
    'type':
    'action.devices.types.SWITCH',
    'willReportState':
    False
}, {
    'id':
    'media_player.living_room',
    'name': {
        'name': 'Living Room'
    },
    'traits':
    ['action.devices.traits.OnOff', 'action.devices.traits.Brightness'],
    'type':
    'action.devices.types.SWITCH',
    'willReportState':
    False
}, {
    'id': 'media_player.lounge_room',
    'name': {
        'name': 'Lounge room'
    },
    'traits': ['action.devices.traits.OnOff'],
    'type': 'action.devices.types.SWITCH',
    'willReportState': False
}, {
    'id':
    'media_player.walkman',
    'name': {
        'name': 'Walkman'
    },
    'traits':
    ['action.devices.traits.OnOff', 'action.devices.traits.Brightness'],
    'type':
    'action.devices.types.SWITCH',
    'willReportState':
    False
}, {
    'id': 'fan.living_room_fan',
    'name': {
        'name': 'Living Room Fan'
    },
    'traits': ['action.devices.traits.OnOff'],
    'type': 'action.devices.types.SWITCH',
    'willReportState': False
}, {
    'id': 'fan.ceiling_fan',
    'name': {
        'name': 'Ceiling Fan'
    },
    'traits': ['action.devices.traits.OnOff'],
    'type': 'action.devices.types.SWITCH',
    'willReportState': False
}, {
    'id': 'group.all_fans',
    'name': {
        'name': 'all fans'
    },
    'traits': ['action.devices.traits.OnOff'],
    'type': 'action.devices.types.SWITCH',
    'willReportState': False
}, {
    'id': 'climate.hvac',
    'name': {
        'name': 'Hvac'
    },
    'traits': ['action.devices.traits.TemperatureSetting'],
    'type': 'action.devices.types.THERMOSTAT',
    'willReportState': False,
    'attributes': {
        'availableThermostatModes': 'heat,cool,heatcool,off',
        'thermostatTemperatureUnit': 'C',
    },
}, {
    'id': 'climate.heatpump',
    'name': {
        'name': 'HeatPump'
    },
    'traits': ['action.devices.traits.TemperatureSetting'],
    'type': 'action.devices.types.THERMOSTAT',
    'willReportState': False
}, {
    'id': 'climate.ecobee',
    'name': {
        'name': 'Ecobee'
    },
    'traits': ['action.devices.traits.TemperatureSetting'],
    'type': 'action.devices.types.THERMOSTAT',
    'willReportState': False
}]
