from flask import Flask, jsonify, request
import json

app = Flask(__name__)

# Initialize device states
devices = {
    "light": False,
    "thermostat": 20  # Default temperature 20°C
}

# Endpoint to get the state of devices
@app.route('/devices', methods=['GET'])
def get_devices():
    return jsonify(devices)

# Endpoint to control devices (local control)
@app.route('/control', methods=['POST'])
def control_device():
    data = request.json
    device = data.get('device')
    state = data.get('state')

    if device in devices:
        devices[device] = state
        return jsonify({"message": f"{device} set to {state}"}), 200
    else:
        return jsonify({"error": "Device not found"}), 404

# Save the device state locally (JSON)
@app.route('/save', methods=['POST'])
def save_state():
    with open('device_state.json', 'w') as file:
        json.dump(devices, file)
    return jsonify({"message": "Device state saved"}), 200

# Load the device state from the local JSON file
@app.route('/load', methods=['GET'])
def load_state():
    global devices
    try:
        with open('device_state.json', 'r') as file:
            devices = json.load(file)
        return jsonify({"message": "Device state loaded", "devices": devices}), 200
    except FileNotFoundError:
        return jsonify({"error": "No saved state found"}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
