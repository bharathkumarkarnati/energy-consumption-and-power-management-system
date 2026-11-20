# SR University Smart Energy Management

A simple Flask web application for the Product 27 project: AI-Assisted Smart Energy Consumption and Power Management System.

## What is included
- Campus structure: 11 blocks, 3 floors per block and 10 rooms per floor (330 rooms).
- 5 laboratories on each first floor (55 labs total).
- 60 desktop computers per lab. Monitor power is included in the desktop estimate; monitors are not listed separately.
- Projectors, fans, lights, air conditioners, UPS/network equipment represented as initial sample inventory where applicable.
- Room-level equipment estimates, manual/API energy reading entry, CSV export, a dashboard, a baseline forecast, statistical anomaly flags and energy-saving suggestions.

## Important data note
The campus structure and equipment values are demonstration assumptions based on the project brief. The app seeds synthetic sample readings so the screens have data on first run. They are labelled `simulated`. Do not present them as actual SR University meter readings. Replace the assumed equipment quantities, rated wattages, hours and tariff with verified data before using the numbers as institutional measurements.

## Run on Windows
Use Python 3.12 (recommended for the supplied dependency versions).

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py
```
Open http://127.0.0.1:5000

The SQLite database is created automatically at first launch. To reset the demo database, stop the server and delete `instance/energy.db`, then start the app again.

## API
`POST /api/readings` accepts JSON:

```json
{
  "room_code": "1101",
  "energy_kwh": 12.5
}
```

A valid request creates an API-sourced reading. The API is intended as a starting point for a meter/IoT integration; no physical meter is connected in this demo.

## Analytics honesty
- Equipment estimates use quantity × rated watts × hours × utilization ÷ 1000.
- Forecast is a recent 7-day average baseline, not a trained machine-learning model.
- Anomaly flags use a simple per-room statistical threshold and should be reviewed by a person.
- Recommendations are rule-based suggestions. The app does not remotely switch equipment.

## Main pages
Overview, Monitoring, Campus, Equipment, Insights and Reports.
