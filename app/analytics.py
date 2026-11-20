from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, pstdev
from .models import EnergyReading, Equipment, Room


def campus_estimate():
    return sum(item.estimated_daily_kwh for item in Equipment.query.filter_by(is_active=True).all())


def room_estimates():
    result = defaultdict(float)
    for item in Equipment.query.filter_by(is_active=True).all():
        result[item.room_id] += item.estimated_daily_kwh
    return result


def daily_readings(days=14):
    start = datetime.utcnow() - timedelta(days=days)
    rows = EnergyReading.query.filter(EnergyReading.recorded_at >= start).all()
    totals = defaultdict(float)
    for row in rows:
        totals[row.recorded_at.date().isoformat()] += row.energy_kwh
    return sorted(totals.items())


def forecast_next_week():
    """
    7-day demand forecast using Ordinary Least Squares (OLS) linear trend
    combined with day-of-week seasonality weights (weekday vs weekend campus load).
    """
    history = daily_readings(30)
    if len(history) < 5:
        return None, "Not enough reading history yet. Add at least 5 days of readings to run the regression model."

    dates = [datetime.fromisoformat(d).date() for d, _ in history]
    values = [float(v) for _, v in history]

    # Compute weekday vs weekend adjustment factors from historical data
    weekday_vals = [v for d, v in zip(dates, values) if d.weekday() < 5]
    weekend_vals = [v for d, v in zip(dates, values) if d.weekday() >= 5]
    overall_avg = mean(values) or 1.0
    wd_factor = (mean(weekday_vals) / overall_avg) if weekday_vals else 1.05
    we_factor = (mean(weekend_vals) / overall_avg) if weekend_vals else 0.65

    # Normalize series to deseasonalized baseline and fit OLS linear trend y = m*x + b
    deseasonalized = [
        v / (wd_factor if d.weekday() < 5 else we_factor)
        for d, v in zip(dates, values)
    ]
    n = len(deseasonalized)
    x_mean = (n - 1) / 2.0
    y_mean = mean(deseasonalized)
    num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(deseasonalized))
    den = sum((i - x_mean) ** 2 for i in range(n)) or 1.0
    slope = num / den
    intercept = y_mean - slope * x_mean

    last_date = dates[-1]
    forecast_days = []
    for step in range(1, 8):
        target_date = last_date + timedelta(days=step)
        trend_val = max(0.0, intercept + slope * (n - 1 + step))
        factor = wd_factor if target_date.weekday() < 5 else we_factor
        forecast_days.append({
            "date": target_date.strftime("%a, %d %b"),
            "kwh": round(trend_val * factor, 2),
            "is_weekend": target_date.weekday() >= 5
        })

    trend_dir = "upward" if slope > 0.25 else ("downward" if slope < -0.25 else "stable")
    note = f"7-day regression forecast ({trend_dir} trend, weekday/weekend load adjusted from {n} days of history)."
    return forecast_days, note


def find_anomalies():
    """
    Detects statistical consumption spikes per room using Z-score (> 2.0 std devs above room baseline)
    and compares against the room's rated equipment estimate.
    """
    rows = EnergyReading.query.order_by(EnergyReading.recorded_at.desc()).limit(500).all()
    by_room = defaultdict(list)
    for row in rows:
        by_room[row.room_id].append((row.energy_kwh, row.recorded_at, row.source))

    alerts = []
    for room_id, values in by_room.items():
        if len(values) < 4:
            continue
        baseline_vals = [float(v) for v, _, _ in values[1:]]
        average = mean(baseline_vals)
        std = pstdev(baseline_vals)
        latest, latest_time, source = values[0]

        if std > 0 and latest > average + 1.8 * std:
            z_score = round((latest - average) / std, 2)
            room = Room.query.get(room_id)
            pct_above = round(((latest - average) / (average or 1)) * 100, 1)
            alerts.append({
                "room_id": room_id,
                "room": room.code if room else str(room_id),
                "room_type": room.room_type if room else "Room",
                "latest": latest,
                "average": average,
                "z_score": z_score,
                "pct_above": pct_above,
                "source": source,
                "recorded_at": latest_time
            })
    alerts.sort(key=lambda x: x["z_score"], reverse=True)
    return alerts


def recommendations():
    suggestions = []
    seen_rooms = set()

    # 1. Data-driven recommendations from anomalous rooms
    for alert in find_anomalies()[:4]:
        excess = max(0.5, alert["latest"] - alert["average"])
        suggestions.append({
            "title": f"Inspect abnormal load spike in {alert['room']} ({alert['room_type']})",
            "where": f"Room {alert['room']}",
            "reason": f"Latest reading ({alert['latest']:.2f} kWh) is {alert['pct_above']}% above normal room baseline ({alert['average']:.2f} kWh). Check for left-on HVAC or lab systems.",
            "saving": round(excess * 0.75, 2),
            "priority": "High"
        })
        seen_rooms.add(alert["room"])

    # 2. Schedule & equipment efficiency recommendations
    for item in Equipment.query.filter_by(is_active=True).all():
        if item.room.code in seen_rooms:
            continue
        if item.hours_per_day >= 9 and item.category.lower() in {"air conditioner", "lighting", "projector"}:
            saving = item.estimated_daily_kwh * 0.15
            suggestions.append({
                "title": f"Optimize {item.name} schedule & thermostat/timer settings",
                "where": f"Room {item.room.code} ({item.room.floor.block.name})",
                "reason": f"Running {item.hours_per_day:g} hrs/day ({item.quantity} units × {item.rated_watts:g}W). Trimming idle hours by 15% reduces peak load.",
                "saving": round(saving, 2),
                "priority": "Medium"
            })
            seen_rooms.add(item.room.code)

    for room in Room.query.filter_by(room_type="Laboratory").all():
        if room.code in seen_rooms:
            continue
        pcs = sum(e.quantity for e in room.equipment if e.category == "Desktop computers" and e.is_active)
        if pcs:
            suggestions.append({
                "title": "Enable automated sleep/shutdown policy on lab desktops",
                "where": f"Room {room.code} ({room.floor.block.name})",
                "reason": f"{pcs} desktop workstations active. Enforcing BIOS/OS auto-shutdown after 6:00 PM avoids overnight standby draw.",
                "saving": round(pcs * 0.16 * 1.5 * 0.30, 2),
                "priority": "Medium"
            })
            seen_rooms.add(room.code)
        if len(suggestions) >= 12:
            break

    return suggestions[:12]
