from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # hashed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(120),unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # hashed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reservations = db.relationship('Reservation', backref='user', lazy=True)

class ParkingLot(db.Model):
    __tablename__ = 'parking_lots'
    id = db.Column(db.Integer, primary_key=True)
    location_name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.Text, nullable=False)
    pin_code = db.Column(db.String(6), nullable=False)
    price_per_hour = db.Column(db.Float, nullable=False)
    max_spots = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Active')  # Active or Inactive
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    spots = db.relationship('ParkingSpot',backref='lot',lazy=True,cascade='all, delete',passive_deletes=True)

class ParkingSpot(db.Model):
    __tablename__ = 'parking_spots'
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lots.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(1), default='A')  # A - Available, O - Occupied
    spot_number = db.Column(db.String(20), nullable=False)  
    reservation = db.relationship('Reservation', backref='spot', lazy=True)
    is_available = db.Column(db.Boolean, default=True)

class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spots.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vehicle_number = db.Column(db.String(20))
    parking_time = db.Column(db.DateTime, default=datetime.utcnow)
    leaving_time = db.Column(db.DateTime, nullable=True)
    cost = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Active')  # Active or Completed

