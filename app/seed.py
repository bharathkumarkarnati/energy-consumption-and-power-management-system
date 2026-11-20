from datetime import datetime, timedelta
import random
from .extensions import db
from .models import Block, Floor, Room, Equipment, EnergyReading, Setting


def seed_data():
    if Block.query.first():
        return
    random.seed(27)
    for b in range(1, 12):
        suffix = "st" if b == 1 else "nd" if b == 2 else "rd" if b == 3 else "th"
        block = Block(name=f"{b}{suffix} Block")
        db.session.add(block)
        db.session.flush()
        for f in range(1, 4):
            floor = Floor(number=f, block_id=block.id)
            db.session.add(floor)
            db.session.flush()
            for r in range(1, 11):
                code = f"{b}{f}{r:02d}"
                room_type = "Laboratory" if f == 1 and r <= 5 else ("Classroom" if r <= 8 else "Office")
                room = Room(code=code, room_type=room_type, floor_id=floor.id)
                db.session.add(room)
                db.session.flush()
                equipment = []
                if room_type == "Laboratory":
                    equipment.extend([
                        ("Lab desktop systems", "Desktop computers", 60, 160, 7, 0.72),
                        ("Laboratory UPS", "UPS", 1, 6000, 7, 0.45),
                    ])
                if room_type in {"Laboratory", "Classroom"}:
                    equipment.extend([
                        ("Projector", "Projector", 1, 300, 6, 0.55),
                        ("Ceiling fans", "Fans", 4, 70, 8, 0.70),
                        ("LED lights", "Lighting", 8, 24, 8, 0.80),
                    ])
                if room_type == "Office":
                    equipment.extend([
                        ("Office fans", "Fans", 3, 70, 8, 0.65),
                        ("Office lights", "Lighting", 5, 24, 8, 0.75),
                    ])
                if r in (1, 2) and f in (2, 3):
                    equipment.append(("Split air conditioner", "Air conditioner", 2, 1800, 10, 0.60))
                if r == 10:
                    equipment.append(("Network switch", "Network switch", 2, 40, 24, 0.80))
                if f == 3 and r == 10:
                    equipment.extend([
                        ("Block server", "Server", 1, 600, 24, 0.55),
                        ("Water pump", "Water pump", 1, 1500, 3, 0.65),
                        ("Server UPS", "UPS", 1, 3000, 24, 0.40),
                    ])
                for name, cat, qty, watts, hours, use in equipment:
                    db.session.add(Equipment(
                        name=name,
                        category=cat,
                        quantity=qty,
                        rated_watts=watts,
                        hours_per_day=hours,
                        utilization=use,
                        room_id=room.id,
                    ))

    db.session.add(Setting(key="tariff_per_kwh", value="8.0"))
    db.session.flush()

    rooms = Room.query.all()
    tracked_rooms = random.sample(rooms, 28)

    # Generate 30 days of realistic weekday/weekend campus meter readings
    for day in range(30, 0, -1):
        dt = datetime.utcnow() - timedelta(days=day)
        is_weekend = dt.weekday() >= 5
        day_factor = 0.55 if is_weekend else 1.0
        for room in tracked_rooms:
            base = sum(e.estimated_daily_kwh for e in room.equipment if e.is_active) / 8.0
            value = max(0.15, base * day_factor * random.uniform(0.85, 1.15))
            db.session.add(EnergyReading(
                recorded_at=dt.replace(hour=14, minute=random.randint(0, 59)),
                energy_kwh=round(value, 2),
                source="simulated",
                note="Simulated daily meter log",
                room_id=room.id,
            ))

    # Inject 3 realistic anomalies on the latest day so anomaly detection demonstrates real behavior
    anomaly_targets = Room.query.filter(Room.code.in_(["1101", "2201", "4103"])).all()
    for room in anomaly_targets:
        for past_day in range(6, 1, -1):
            base = sum(e.estimated_daily_kwh for e in room.equipment if e.is_active) / 8.0
            db.session.add(EnergyReading(
                recorded_at=datetime.utcnow() - timedelta(days=past_day),
                energy_kwh=round(base * random.uniform(0.9, 1.08), 2),
                source="simulated",
                note="Simulated baseline reading",
                room_id=room.id,
            ))
        spike_base = sum(e.estimated_daily_kwh for e in room.equipment if e.is_active) / 8.0
        db.session.add(EnergyReading(
            recorded_at=datetime.utcnow() - timedelta(hours=1),
            energy_kwh=round(spike_base * 1.95, 2),
            source="simulated",
            note="Unusual spike (equipment left running overnight)",
            room_id=room.id,
        ))

    db.session.commit()
