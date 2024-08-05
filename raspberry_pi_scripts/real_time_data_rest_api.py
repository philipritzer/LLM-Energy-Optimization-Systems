from datetime import datetime

import pytz
import requests
import urllib3
from flask import Flask, jsonify

import myconfig

app = Flask(__name__)

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_KEY = myconfig.SOLAR_API_KEY


def fetch_data(url, headers):
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        return response.json()
    else:
        app.logger.error(f"Failed to fetch data from API. Status code: {response.status_code}")
        return None


def fetch_solar_data():
    url = "https://192.168.178.170/ivp/meters/reports"
    headers = {
        'Authorization': API_KEY,
        'Accept': 'application/json'
    }
    return fetch_data(url, headers)


def fetch_inventory_data():
    url = "https://192.168.178.170/ivp/ensemble/inventory"
    headers = {
        'Authorization': API_KEY,
        'Accept': 'application/json'
    }
    return fetch_data(url, headers)


def extract_relevant_data(data):
    if not data:
        return None

    production_power = None
    net_consumption_power = None
    total_consumption_power = None

    for entry in data:
        report_type = entry.get('reportType')
        act_power = entry.get('cumulative', {}).get('actPower', None)

        if report_type == 'production':
            production_power = act_power
        elif report_type == 'net-consumption':
            net_consumption_power = act_power
        elif report_type == 'total-consumption':
            total_consumption_power = act_power

    utc_time = datetime.utcnow()
    timestamp = pytz.timezone('Europe/Berlin').fromutc(utc_time)

    return {
        "timestamp": timestamp.isoformat(),
        "production_power": round(production_power / 1000, 1) if production_power else None,
        "net_consumption_power": round(net_consumption_power / 1000, 1) if net_consumption_power else None,
        "total_consumption_power": round(total_consumption_power / 1000, 1) if total_consumption_power else None
    }


def extract_inventory_data(data):
    if not data:
        return None

    percent_full = None

    for entry in data:
        if entry.get('type') == 'ENCHARGE':
            devices = entry.get('devices', [])
            if devices:
                percent_full = devices[0].get('percentFull', None)
                break

    return percent_full


@app.route('/solar-data', methods=['GET'])
def get_solar_data():
    raw_solar_data = fetch_solar_data()
    relevant_solar_data = extract_relevant_data(raw_solar_data)

    raw_inventory_data = fetch_inventory_data()
    relevant_inventory_data = extract_inventory_data(raw_inventory_data)

    if relevant_solar_data and relevant_inventory_data is not None:
        response_data = {
            **relevant_solar_data,
            "battery_status": relevant_inventory_data
        }
        return jsonify(response_data), 200
    else:
        return jsonify({"error": "Failed to fetch or process data"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
