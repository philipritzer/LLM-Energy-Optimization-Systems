import csv
import datetime
import io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from firebase_functions import https_fn
from flask import Flask, Response, jsonify

cred = credentials.Certificate("auth.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

app = Flask(__name__)


def to_zoned_time(timestamp, timezone):
    return timestamp.replace(tzinfo=ZoneInfo(timezone))


def format_datetime(dt, format_string, timezone):
    return dt.astimezone(ZoneInfo(timezone)).strftime(format_string)


@app.route('/solarcsv')
def get_solar_data_three_days_csv():
    try:
        all_entries = []
        three_days_ago = datetime.now(ZoneInfo("UTC")) - timedelta(days=3)

        query_snapshot = db.collection("SolarDataV1").where("timestamp", ">=", three_days_ago).get()

        for doc in query_snapshot:
            data = doc.to_dict()
            timestamp = data['timestamp'].astimezone(ZoneInfo("Europe/Berlin"))
            formatted_data = {
                **data,
                'timestamp': timestamp.strftime("%Y-%m-%dT%H:%M")
            }

            all_entries.append(formatted_data)

        if not all_entries:
            return "No data available", 404

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=all_entries[0].keys())
        writer.writeheader()
        writer.writerows(all_entries)

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=solar_data.csv"}
        )

    except Exception as error:
        print(f"Error fetching data: {error}")
        return "We found an error fetching your request!", 500


@app.route('/dailysums')
def get_daily_sums_last_three_days():
    try:
        three_days_ago = datetime.now(ZoneInfo("Europe/Berlin")) - timedelta(days=3)
        three_days_ago = three_days_ago.replace(hour=0, minute=0, second=0, microsecond=0)

        query_snapshot = db.collection("SolarDataV1").where("timestamp", ">=", three_days_ago).get()

        daily_data = {}

        for doc in query_snapshot:
            data = doc.to_dict()
            timestamp = data['timestamp'].astimezone(ZoneInfo("Europe/Berlin"))
            day_key = timestamp.date().isoformat()
            hour_key = timestamp.hour

            if day_key not in daily_data:
                daily_data[day_key] = {
                    'consumption': {'pos': [0] * 24, 'pos_count': [0] * 24},
                    'grid': {'pos': [0] * 24, 'neg': [0] * 24, 'pos_count': [0] * 24, 'neg_count': [0] * 24},
                    'production': {'pos': [0] * 24, 'pos_count': [0] * 24}
                }

            for field in ['consumption', 'grid', 'production']:
                if field in data:
                    value = data[field]
                    if field == 'grid':
                        if value >= 0:
                            daily_data[day_key][field]['pos'][hour_key] += value
                            daily_data[day_key][field]['pos_count'][hour_key] += 1
                        else:
                            daily_data[day_key][field]['neg'][hour_key] += value
                            daily_data[day_key][field]['neg_count'][hour_key] += 1
                    elif value > 0:
                        daily_data[day_key][field]['pos'][hour_key] += value
                        daily_data[day_key][field]['pos_count'][hour_key] += 1

        result = []
        for day, data in daily_data.items():
            day_sums = {'date': day}
            for field in ['consumption', 'grid', 'production']:
                pos_total = 0
                for hour in range(24):
                    if data[field]['pos_count'][hour] > 0:
                        pos_total += data[field]['pos'][hour] / data[field]['pos_count'][hour]
                day_sums[f'{field}_positive'] = round(pos_total, 2)

                if field == 'grid':
                    neg_total = 0
                    for hour in range(24):
                        if data[field]['neg_count'][hour] > 0:
                            neg_total += data[field]['neg'][hour] / data[field]['neg_count'][hour]
                    day_sums[f'{field}_negative'] = round(neg_total, 2)

            result.append(day_sums)

        return jsonify(result)

    except Exception as error:
        print(f"Error calculating daily sums: {error}")
        return f"We found an error calculating daily sums: {str(error)}", 500


@https_fn.on_request()
def solar_data_function(request):
    with app.request_context(request.environ):
        return app.full_dispatch_request()
