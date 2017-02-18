"""
generate test data for migardener the built in MQTT server

"""

import yaml
import os
import paho.mqtt.client as mqtt
import time

ATTRIBUTES = {
    'battery': (0, 100, 5),
    'temperature': (-20.0, 30.0, 5.3),
    'brightness': (0, 10000, 500),
    'moisture': (0, 100, 5),
    'conductivity': (0, 2000, 200),
}


def main():
    config_path = os.path.expanduser('~/.homeassistant/configuration.yaml')
    with open(config_path,'r' ) as config_file:
        config = yaml.load(config_file)
    api_password = config['http']['api_password']

    client = mqtt.Client()
    client.username_pw_set('homeassistant', api_password)
    client.connect('localhost',port=1883)
    client.loop_start()

    values = dict()
    for name,params in ATTRIBUTES.items():
        values[name] = params[0]

    while True:
        for name,params in ATTRIBUTES.items():
            values[name] = (values[name] + params[2]) % params[1]
            client.publish('test/simulated_plant/{}'.format(name),values[name])
            print('published {}={}'.format(name,values[name]))
        time.sleep(5)


if __name__ == '__main__':
    main()