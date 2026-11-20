from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from sqlalchemy import func
from .extensions import db
from .models import Block, Floor, Room, Equipment, EnergyReading, Setting
from .analytics import campus_estimate, daily_readings, forecast_next_week, find_anomalies, recommendations

bp = Blueprint("main", __name__)


@bp.app_template_filter("num")
def num(value):
    return f"{value:,.2f}"


@bp.route("/")
def dashboard():
    total_est = campus_estimate()
    today = datetime.utcnow().date()
    actual_today = (
        db.session.query(func.sum(EnergyReading.energy_kwh))
        .filter(func.date(EnergyReading.recorded_at) == today)
        .scalar()
        or 0
    )
    latest = EnergyReading.query.order_by(EnergyReading.recorded_at.desc()).limit(7).all()
    top_blocks = []
    for block in Block.query.all():
        room_ids = [r.id for f in block.floors for r in f.rooms]
        estimated = (
            sum(
                e.estimated_daily_kwh
                for e in Equipment.query.filter(
                    Equipment.room_id.in_(room_ids), Equipment.is_active == True
                ).all()
            )
            if room_ids
            else 0
        )
        top_blocks.append((block.id, block.name, estimated))
    top_blocks.sort(key=lambda x: x[2], reverse=True)
    forecast, forecast_note = forecast_next_week()
    alerts = find_anomalies()
    trend_14d = daily_readings(14)
    return render_template(
        "dashboard.html",
        total_est=total_est,
        actual_today=actual_today,
        latest=latest,
        top_blocks=top_blocks[:5],
        forecast=forecast,
        forecast_note=forecast_note,
        alerts=alerts[:5],
        recommendation_count=len(recommendations()),
        trend_14d=trend_14d,
    )


@bp.route("/campus")
def campus():
    blocks = Block.query.order_by(Block.id).all()
    block_stats = {}
    for b in blocks:
        room_ids = [r.id for f in b.floors for r in f.rooms]
        est = sum(
            e.estimated_daily_kwh
            for e in Equipment.query.filter(
                Equipment.room_id.in_(room_ids), Equipment.is_active == True
            ).all()
        )
        block_stats[b.id] = est
    return render_template("campus.html", blocks=blocks, block_stats=block_stats)


@bp.route("/block/<int:block_id>")
def block_detail(block_id):
    block = Block.query.get_or_404(block_id)
    return render_template("block.html", block=block)


@bp.route("/room/<int:room_id>")
def room_detail(room_id):
    room = Room.query.get_or_404(room_id)
    readings = (
        EnergyReading.query.filter_by(room_id=room.id)
        .order_by(EnergyReading.recorded_at.desc())
        .limit(20)
        .all()
    )
    return render_template("room.html", room=room, readings=readings)


@bp.route("/monitoring", methods=["GET", "POST"])
def monitoring():
    if request.method == "POST":
        room = Room.query.filter_by(code=request.form.get("room_code", "").strip()).first()
        try:
            value = float(request.form.get("energy_kwh", ""))
            if not room or value <= 0:
                raise ValueError
            recorded = (
                datetime.fromisoformat(request.form["recorded_at"])
                if request.form.get("recorded_at")
                else datetime.utcnow()
            )
            note = request.form.get("note", "").strip() or "Manually entered reading"
            db.session.add(
                EnergyReading(
                    room_id=room.id,
                    energy_kwh=value,
                    recorded_at=recorded,
                    source="manual",
                    note=note[:200],
                )
            )
            db.session.commit()
            flash(f"Saved {value:.2f} kWh reading for Room {room.code}.", "success")
        except (ValueError, KeyError):
            flash("Enter a valid room code (e.g. 1101) and a positive kWh value.", "error")
        return redirect(url_for("main.monitoring"))
    readings = EnergyReading.query.order_by(EnergyReading.recorded_at.desc()).limit(60).all()
    rooms = Room.query.order_by(Room.code).all()
    return render_template("monitoring.html", readings=readings, rooms=rooms)


@bp.route("/equipment", methods=["GET", "POST"])
def equipment():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "toggle":
            item = Equipment.query.get_or_404(int(request.form.get("item_id", 0)))
            item.is_active = not item.is_active
            db.session.commit()
            flash(f"Updated status for {item.name} in Room {item.room.code}.", "success")
        elif action == "add":
            room = Room.query.filter_by(code=request.form.get("room_code", "").strip()).first()
            try:
                name = request.form.get("name", "").strip()
                category = request.form.get("category", "").strip() or "Other"
                qty = int(request.form.get("quantity", 1))
                watts = float(request.form.get("rated_watts", 0))
                hours = float(request.form.get("hours_per_day", 8))
                if not room or not name or qty <= 0 or watts <= 0 or hours <= 0:
                    raise ValueError
                db.session.add(
                    Equipment(
                        name=name,
                        category=category,
                        quantity=qty,
                        rated_watts=watts,
                        hours_per_day=hours,
                        utilization=0.70,
                        room_id=room.id,
                    )
                )
                db.session.commit()
                flash(f"Added {name} to Room {room.code}.", "success")
            except ValueError:
                flash("Please provide valid room code, equipment name, quantity, wattage, and hours.", "error")
        return redirect(url_for("main.equipment"))

    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    query = Equipment.query.join(Room)
    if q:
        query = query.filter(
            (Room.code.ilike(f"%{q}%")) | (Equipment.name.ilike(f"%{q}%"))
        )
    if cat:
        query = query.filter(Equipment.category == cat)
    items = query.order_by(Room.code, Equipment.category).limit(200).all()
    categories = [c[0] for c in db.session.query(Equipment.category).distinct().order_by(Equipment.category).all()]
    return render_template("equipment.html", items=items, categories=categories, q=q, selected_cat=cat)


@bp.route("/insights")
def insights():
    forecast, note = forecast_next_week()
    alerts = find_anomalies()
    suggestions = recommendations()
    return render_template(
        "insights.html",
        forecast=forecast,
        forecast_note=note,
        alerts=alerts,
        suggestions=suggestions,
    )


@bp.route("/reports", methods=["GET", "POST"])
def reports():
    tariff_setting = Setting.query.filter_by(key="tariff_per_kwh").first()
    if request.method == "POST":
        try:
            new_tariff = float(request.form.get("tariff", ""))
            if new_tariff <= 0:
                raise ValueError
            tariff_setting.value = f"{new_tariff:.2f}"
            db.session.commit()
            flash(f"Electricity tariff updated to ₹{new_tariff:.2f}/kWh.", "success")
        except ValueError:
            flash("Enter a valid positive electricity rate.", "error")
        return redirect(url_for("main.reports"))

    rows = daily_readings(30)
    tariff = float(tariff_setting.value) if tariff_setting else 8.0
    total_kwh = sum(v for _, v in rows)
    return render_template("reports.html", rows=rows, tariff=tariff, total_kwh=total_kwh)


@bp.route("/api/readings", methods=["GET", "POST"])
def api_reading():
    if request.method == "GET":
        rows = EnergyReading.query.order_by(EnergyReading.recorded_at.desc()).limit(25).all()
        return jsonify([
            {
                "id": r.id,
                "room_code": r.room.code,
                "energy_kwh": r.energy_kwh,
                "source": r.source,
                "recorded_at": r.recorded_at.isoformat(),
                "note": r.note,
            }
            for r in rows
        ])

    data = request.get_json(silent=True) or {}
    room = Room.query.filter_by(code=str(data.get("room_code", "")).strip()).first()
    try:
        value = float(data.get("energy_kwh"))
        if not room or value <= 0:
            raise ValueError
        note = str(data.get("note", "Received via IoT/Meter API"))[:200]
        row = EnergyReading(room_id=room.id, energy_kwh=value, source="api", note=note)
        db.session.add(row)
        db.session.commit()
        return jsonify({"message": "Reading saved", "id": row.id, "room_code": room.code}), 201
    except (TypeError, ValueError):
        return jsonify({"error": "Provide a valid room_code and positive energy_kwh"}), 400


@bp.route("/api/summary")
def api_summary():
    forecast, note = forecast_next_week()
    return jsonify({
        "estimated_daily_kwh": round(campus_estimate(), 2),
        "total_rooms": Room.query.count(),
        "active_anomalies": len(find_anomalies()),
        "forecast_note": note,
        "forecast_7_days": forecast,
    })


@bp.route("/export.csv")
def export_csv():
    rows = EnergyReading.query.join(Room).order_by(EnergyReading.recorded_at.desc()).all()
    lines = ["recorded_at,room_code,energy_kwh,source,note"]
    for row in rows:
        clean_note = (row.note or "").replace(",", " ")
        lines.append(f"{row.recorded_at.isoformat()},{row.room.code},{row.energy_kwh},{row.source},{clean_note}")
    return Response(
        "\n".join(lines),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=sru_energy_readings.csv"},
    )
