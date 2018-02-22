"""Script to convert an old-structure influxdb to a new one."""

import argparse
import sys

from typing import List


# Based on code at
# http://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console
def print_progress(iteration: int, total: int, prefix: str = '',
                   suffix: str = '', decimals: int = 2,
                   bar_length: int = 68) -> None:
    """Print progress bar.

    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : number of decimals in percent complete (Int)
        barLength   - Optional  : character length of bar (Int)
    """
    filled_length = int(round(bar_length * iteration / float(total)))
    percents = round(100.00 * (iteration / float(total)), decimals)
    line = '#' * filled_length + '-' * (bar_length - filled_length)
    sys.stdout.write('%s [%s] %s%s %s\r' % (prefix, line,
                                            percents, '%', suffix))
    sys.stdout.flush()
    if iteration == total:
        print("\n")


def run(script_args: List) -> int:
    """Run the actual script."""
    from influxdb import InfluxDBClient

    parser = argparse.ArgumentParser(
        description="Migrate legacy influxDB.")
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
        help="How many points to migrate at the same time")
    parser.add_argument(
        '-o', '--override-measurement',
        metavar='override_measurement',
        default="",
        help="Store all your points in the same measurement")
    parser.add_argument(
        '-D', '--delete',
        action='store_true',
        default=False,
        help="Delete old database")
    parser.add_argument(
        '--script',
        choices=['influxdb_migrator'])

    args = parser.parse_args()

    # Get client for old DB
    client = InfluxDBClient(args.host, args.port,
                            args.username, args.password)
    client.switch_database(args.dbname)
    # Get DB list
    db_list = [db['name'] for db in client.get_list_database()]
    # Get measurements of the old DB
    res = client.query('SHOW MEASUREMENTS')
    measurements = [measurement['name'] for measurement in res.get_points()]
    nb_measurements = len(measurements)
    # Move data
    # Get old DB name
    old_dbname = "{}__old".format(args.dbname)
    # Create old DB if needed
    if old_dbname not in db_list:
        client.create_database(old_dbname)
    # Copy data to the old DB
    print("Cloning from {} to {}".format(args.dbname, old_dbname))
    for index, measurement in enumerate(measurements):
        client.query('''SELECT * INTO {}..:MEASUREMENT FROM '''
                     '"{}" GROUP BY *'.format(old_dbname, measurement))
        # Print progress
        print_progress(index + 1, nb_measurements)

    # Delete the database
    client.drop_database(args.dbname)
    # Create new DB if needed
    client.create_database(args.dbname)
    client.switch_database(old_dbname)
    # Get client for new DB
    new_client = InfluxDBClient(args.host, args.port, args.username,
                                args.password, args.dbname)
    # Counter of points without time
    point_wt_time = 0

    print("Migrating from {} to {}".format(old_dbname, args.dbname))
    # Walk into measurement
    for index, measurement in enumerate(measurements):

        # Get tag list
        res = client.query('''SHOW TAG KEYS FROM "{}"'''.format(measurement))
        tags = [v['tagKey'] for v in res.get_points()]
        # Get field list
        res = client.query('''SHOW FIELD KEYS FROM "{}"'''.format(measurement))
        fields = [v['fieldKey'] for v in res.get_points()]
        # Get points, convert and send points to the new DB
        offset = 0
        while True:
            nb_points = 0
            # Prepare new points
            new_points = []
            # Get points
            res = client.query('SELECT * FROM "{}" LIMIT {} OFFSET '
                               '{}'.format(measurement, args.step, offset))
            for point in res.get_points():
                new_point = {"tags": {},
                             "fields": {},
                             "time": None}
                if args.override_measurement:
                    new_point["measurement"] = args.override_measurement
                else:
                    new_point["measurement"] = measurement
                # Check time
                if point["time"] is None:
                    # Point without time
                    point_wt_time += 1
                    print("Can not convert point without time")
                    continue
                # Convert all fields
                for field in fields:
                    try:
                        new_point["fields"][field] = float(point[field])
                    except (ValueError, TypeError):
                        if field == "value":
                            new_key = "state"
                        else:
                            new_key = "{}_str".format(field)
                        new_point["fields"][new_key] = str(point[field])
                # Add tags
                for tag in tags:
                    new_point["tags"][tag] = point[tag]
                # Set time
                new_point["time"] = point["time"]
                # Add new point to the new list
                new_points.append(new_point)
                # Count nb points
                nb_points += 1

            # Send to the new db
            try:
                new_client.write_points(new_points)
            except Exception as exp:
                raise exp

            # If there is no points
            if nb_points == 0:
                # print("Measurement {} migrated".format(measurement))
                break
            else:
                # Increment offset
                offset += args.step
        # Print progress
        print_progress(index + 1, nb_measurements)

    # Delete database if needed
    if args.delete:
        print("Dropping {}".format(old_dbname))
        client.drop_database(old_dbname)
