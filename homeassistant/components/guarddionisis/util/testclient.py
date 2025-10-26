import grpc
import sensor_pb2
import sensor_pb2_grpc

def run():
    with grpc.insecure_channel('localhost:52751') as channel:
        stub = sensor_pb2_grpc.SensorServiceStub(channel)

        # Get sensor data
        # response = stub.GetSensorData(sensor_pb2.Empty())
        # print(f"Received sensor data: ID={response.id}, Value={response.value}")

        # Set new sensor data
        new_data = sensor_pb2.SensorData(entity_id="sensor.homealarm", value=3)
        stub.SetSensorData(new_data)
        print("Set new sensor data.")

        # Get updated sensor data
        # response = stub.GetSensorData(sensor_pb2.Empty())
        # print(f"Received updated sensor data: ID={response.id}, Value={response.value}")

if __name__ == '__main__':
    run()
