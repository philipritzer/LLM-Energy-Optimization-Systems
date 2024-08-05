import urllib3
import firebase_admin
from firebase_admin import credentials, firestore, db as realtime_db
import requests
from datetime import datetime
import myconfig
import pytz

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

cred = credentials.Certificate('auth.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': myconfig.database_url
})

firestore_db = firestore.client()


def fetch_data(url, headers):
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data from API. Status code: {response.status_code}")
        return None


def fetch_solar_data():
    url = "https://192.168.178.170/ivp/meters/reports"
    headers = {
        'Authorization': myconfig.SOLAR_API_KEY,
        'Accept': 'application/json'
    }
    return fetch_data(url, headers)


def fetch_inventory_data():
    url = "https://192.168.178.170/ivp/ensemble/inventory"
    headers = {
        'Authorization': myconfig.SOLAR_API_KEY,
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
    document_id = timestamp.strftime('%Y-%m-%d::%H:%M:%S')

    return {
        "document_id": document_id,
        "timestamp": timestamp,
        "production_power": round(production_power/1000, 1),
        "net_consumption_power": round(net_consumption_power/1000, 1),
        "total_consumption_power": round(total_consumption_power/1000, 1)
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


def store_data_in_firestore(data, inventory_data):
    if data:
        doc_ref = firestore_db.collection('SolarDataV1').document(data["document_id"])
        doc_ref.set({
            "timestamp": data["timestamp"],
            "production": data["production_power"],
            "grid": data["net_consumption_power"],
            "consumption": data["total_consumption_power"],
            "battery_status": inventory_data
        })
        print("Data stored successfully in Firestore")

        with open("data_log.txt", "a") as log_file:
            log_file.write(f"{data['timestamp']}: Data stored successfully in Firestore\n")
    else:
        print("No data to store in Firestore")


def store_data_in_realtime_database(data, inventory_data):
    if data:
        ref = realtime_db.reference('SolarData')
        ref.child(data["document_id"]).set({
            "timestamp": data["timestamp"].isoformat(),
            "production": data["production_power"],
            "grid": data["net_consumption_power"],
            "consumption": data["total_consumption_power"],
            "battery_status": inventory_data
        })
        print("Data stored successfully in Realtime Database")

        with open("data_log.txt", "a") as log_file:
            log_file.write(f"{data['timestamp']}: Data stored successfully in Realtime Database\n")
    else:
        print("No data to store in Realtime Database")


if __name__ == "__main__":
    raw_solar_data = fetch_solar_data()
    relevant_solar_data = extract_relevant_data(raw_solar_data)

    raw_inventory_data = fetch_inventory_data()
    relevant_inventory_data = extract_inventory_data(raw_inventory_data)

    store_data_in_firestore(relevant_solar_data, relevant_inventory_data)
    store_data_in_realtime_database(relevant_solar_data, relevant_inventory_data)
