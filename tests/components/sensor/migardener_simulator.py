"""Generate test data for migardener the built in MQTT server.

This program will mock a plant gatway
(https://github.com/ChristianKuehnel/plantgateway) and send data
in short intervals to the build-in MQTT server of Home Assistant instance.

It can be used for testing the data input and processing in the
migardener.py sensor.
"""

import yaml
import os
import paho.mqtt.client as mqtt
import time
import json

"""data used in simulating the different measurements of the sensor.
first entry: min value
second entry: max value
third entry: increment
"""
ATTRIBUTES = {

    'battery': (0, 100, 5),
    'temperature': (-20.0, 30.0, 5.3),
    'brightness': (0, 10000, 400),
    'moisture': (0, 100, 5),
    'conductivity': (0, 2000, 300),
}


def main():
    """Main method, will mock the plant gateway."""
    config_path = os.path.expanduser('~/.homeassistant/configuration.yaml')
    with open(config_path, 'r') as config_file:
        config = yaml.load(config_file)
    api_password = config['http']['api_password']

    client = mqtt.Client()
    client.username_pw_set('homeassistant', api_password)
    client.connect('localhost', port=1883)
    client.loop_start()

    values = dict()
    for name, params in ATTRIBUTES.items():
        values[name] = params[0]

    while True:
        for name, params in ATTRIBUTES.items():
            values[name] = (values[name] + params[2]) % params[1]
        json_payload = json.dumps(values)
        client.publish('test/simulated_plant', json_payload)
        print('published {}'.format(json_payload))
        time.sleep(5)


if __name__ == '__main__':
    main()
