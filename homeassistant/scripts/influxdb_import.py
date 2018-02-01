"""Script to import recorded data into influxdb."""
import argparse
import json
import os

from typing import List

import homeassistant.config as config_util


def run(script_args: List) -> int:
    """Run the actual script."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from influxdb import InfluxDBClient
    from homeassistant.components.recorder import models
    from homeassistant.helpers import state as state_helper
    from homeassistant.core import State

    parser = argparse.ArgumentParser(
        description="import data to influxDB.")
    parser.add_argument(
        '-c', '--config',
        metavar='path_to_config_dir',
        default=config_util.get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration")
    parser.add_argument(
        '--uri',
        type=str,
        help="Connect to URI and import (if other than default sqlite) "
             "eg: mysql://localhost/homeassistant")
    parser.add_argument(
        '-d', '--dbname',
        metavar='dbname',
        required=True,
        help="InfluxDB database name")
    parser.add_argument(
        '-H', '--host',
        metavar='host',
        default='127.0.0.1',
        help="InfluxDB host address")
    parser.add_argument(
        '-P', '--port',
        metavar='port',
        default=8086,
        help="InfluxDB host port")
    parser.add_argument(
        '-u', '--username',
        metavar='username',
        default='root',
        help="InfluxDB username")
    parser.add_argument(
        '-p', '--password',
        metavar='password',
        default='root',
        help="InfluxDB password")
    parser.add_argument(
        '-s', '--step',
        metavar='step',
        default=1000,
        help="How many points to import at the same time")
    parser.add_argument(
        '-t', '--tags',
        metavar='tags',
        default="",
        help="Comma separated list of tags (key:value) for all points")
    parser.add_argument(
        '-D', '--default-measurement',
        metavar='default_measurement',
        default="",
        help="Store all your points in the same measurement")
    parser.add_argument(
        '-o', '--override-measurement',
        metavar='override_measurement',
        default="",
        help="Store all your points in the same measurement")
    parser.add_argument(
        '-e', '--exclude_entities',
        metavar='exclude_entities',
        default="",
        help="Comma separated list of excluded entities")
    parser.add_argument(
        '-E', '--exclude_domains',
        metavar='exclude_domains',
        default="",
        help="Comma separated list of excluded domains")
    parser.add_argument(
        "-S", "--simulate",
        default=False,
        action="store_true",
        help=("Do not write points but simulate preprocessing and print "
              "statistics"))
    parser.add_argument(
        '--script',
        choices=['influxdb_import'])

    args = parser.parse_args()
    simulate = args.simulate

    client = None
    if not simulate:
        client = InfluxDBClient(args.host, args.port,
                                args.username, args.password)
        client.switch_database(args.dbname)

    config_dir = os.path.join(os.getcwd(), args.config)  # type: str

    # Test if configuration directory exists
    if not os.path.isdir(config_dir):
        if config_dir != config_util.get_default_config_dir():
            print(('Fatal Error: Specified configuration directory does '
                   'not exist {} ').format(config_dir))
            return 1

    src_db = '{}/home-assistant_v2.db'.format(config_dir)

    if not os.path.exists(src_db) and not args.uri:
        print("Fatal Error: Database '{}' does not exist "
              "and no uri given".format(src_db))
        return 1

    uri = args.uri or "sqlite:///{}".format(src_db)
    engine = create_engine(uri, echo=False)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    step = int(args.step)

    tags = {}
    if args.tags:
        tags.update(dict(elem.split(":") for elem in args.tags.split(",")))
    excl_entities = args.exclude_entities.split(",")
    excl_domains = args.exclude_domains.split(",")
    override_measurement = args.override_measurement
    default_measurement = args.default_measurement

    query = session.query(models.Events).filter(
        models.Events.event_type == "state_changed").order_by(
            models.Events.time_fired)

    points = []
    count = 0
    from collections import defaultdict
    entities = defaultdict(int)

    for event in query:
        event_data = json.loads(event.event_data)
        state = State.from_dict(event_data.get("new_state"))

        if not state or (
                excl_entities and state.entity_id in excl_entities) or (
                    excl_domains and state.domain in excl_domains):
            session.expunge(event)
            continue

        try:
            _state = float(state_helper.state_as_number(state))
            _state_key = "value"
        except ValueError:
            _state = state.state
            _state_key = "state"

        if override_measurement:
            measurement = override_measurement
        else:
            measurement = state.attributes.get('unit_of_measurement')
            if measurement in (None, ''):
                if default_measurement:
                    measurement = default_measurement
                else:
                    measurement = state.entity_id

        point = {
            'measurement': measurement,
            'tags': {
                'domain': state.domain,
                'entity_id': state.object_id,
            },
            'time': event.time_fired,
            'fields': {
                _state_key: _state,
            }
        }

        for key, value in state.attributes.items():
            if key != 'unit_of_measurement':
                # If the key is already in fields
                if key in point['fields']:
                    key = key + "_"
                # Prevent column data errors in influxDB.
                # For each value we try to cast it as float
                # But if we can not do it we store the value
                # as string add "_str" postfix to the field key
                try:
                    point['fields'][key] = float(value)
                except (ValueError, TypeError):
                    new_key = "{}_str".format(key)
                    point['fields'][new_key] = str(value)

        entities[state.entity_id] += 1
        point['tags'].update(tags)
        points.append(point)
        session.expunge(event)
        if len(points) >= step:
            if not simulate:
                print("Write {} points to the database".format(len(points)))
                client.write_points(points)
            count += len(points)
            points = []

    if points:
        if not simulate:
            print("Write {} points to the database".format(len(points)))
            client.write_points(points)
        count += len(points)

    print("\nStatistics:")
    print("\n".join(["{:6}: {}".format(v, k) for k, v
                     in sorted(entities.items(), key=lambda x: x[1])]))
    print("\nImport finished {} points written".format(count))
    return 0
