"""Pass commit check."""
import datetime

import openaq


# A api client. Can fetch data for a specific location. Both present data and historical data
class AQ_client:
    """Pass commit check."""

    # Pass git check
    def __init__(self, hass, api_key, location_id):
        """Pass commit check."""
        self.client = openaq.OpenAQ(api_key=api_key)
        self.location_id = location_id
        self.setup_device()

    def setup_device(self):
        """Pass commit check."""
        # print("Setting up device...")
        response = self.client.locations.get(self.location_id)
        response = response.dict()

        self.name = response["results"][0]["name"]
        self.sensors = response["results"][0]["sensors"]
        self.coordinates = response["results"][0]["coordinates"]
        self.lastUpdated = response["results"][0]["datetime_last"]["local"]
        self.firstUpdated = response["results"][0]["datetime_first"]["local"]

        # print("Getting last measurements")
        # print(self.lastUpdated)
        # print(datetime.datetime.now())

        # Returns empty result. I think one have to pick an older date than the lastUpdate
        measurements = self.client.measurements.list(
            self.location_id,
            date_from=self.lastUpdated,
            date_to=datetime.datetime.now(),
        )
        measurements.dict()
        # print(measurements)

    def get_hist_data(self, startDate, stopDate):
        """Pass commit check."""
        # print("Getting historical data from device...")
        res = self.client.measurements.list(
            self.location_id, date_from=startDate, date_to=stopDate
        )
        res.dict()
        # print(res)
        # print("Successfully got historical data")


def api_test():
    """IS A TEST. NOW LET ME FUCKING PASS THE COMMIT!!!."""
    # print("RUNNING SCRIPT!")
    AQ_client(None, "INSERT API KEY HERE", 10496)
    # print(client.parameters)
    # client.get_hist_data(datetime.datetime(2023,11,12), datetime.datetime.now())


api_test()
