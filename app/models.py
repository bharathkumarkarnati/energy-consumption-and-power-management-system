from datetime import datetime
from .extensions import db

class Block(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    floors = db.relationship("Floor", backref="block", cascade="all, delete-orphan")

class Floor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    block_id = db.Column(db.Integer, db.ForeignKey("block.id"), nullable=False)
    rooms = db.relationship("Room", backref="floor", cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("number", "block_id"),)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    room_type = db.Column(db.String(30), nullable=False)
    floor_id = db.Column(db.Integer, db.ForeignKey("floor.id"), nullable=False)
    equipment = db.relationship("Equipment", backref="room", cascade="all, delete-orphan")

class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    rated_watts = db.Column(db.Float, nullable=False)
    hours_per_day = db.Column(db.Float, default=8, nullable=False)
    utilization = db.Column(db.Float, default=0.65, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)

    @property
    def estimated_daily_kwh(self):
        return self.quantity * self.rated_watts * self.hours_per_day * self.utilization / 1000

class EnergyReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recorded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    energy_kwh = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(20), nullable=False, default="simulated")
    note = db.Column(db.String(200))
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    room = db.relationship("Room", backref="readings")

class Setting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(100), nullable=False)
