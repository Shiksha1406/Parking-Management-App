from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


db=SQLAlchemy()

class user_info(db.Model):
    __tablename__ = 'user_info'

    id = db.Column(db.Integer, primary_key=True)
    email=db.Column(db.String,nullable=False)
    fullname=db.Column(db.String,nullable=False)
    password=db.Column(db.String,nullable=False)
    Address=db.Column(db.String,nullable=False)
    Pincode=db.Column(db.String(6),nullable=False)
    role = db.Column(db.Integer, nullable=False, default=1)

    reservations = db.relationship('reservation', back_populates='user')
    

class parking_lot(db.Model):
    __tablename__ = 'parking_lot'

    id = db.Column(db.Integer, primary_key=True)
    prime_location_name = db.Column(db.String,nullable=False)
    price = db.Column(db.Integer,nullable=False)
    Address = db.Column(db.String,nullable=False)
    Pincode = db.Column(db.String(6),nullable=False)
    maximum_number_of_spots = db.Column(db.Integer,nullable=False)

    spots=db.relationship('parking_spot',backref='lot',lazy=True)
    reservations = db.relationship('reservation', back_populates='lot',foreign_keys='reservation.lot_id')

    @property
    def free_spots(self):
        return sum(1 for spot in self.spots if spot.status == 'A') 
    
    @property
    def occupied_spots(self):
        return sum(1 for s in self.spots if s.status == 'O')

class parking_spot(db.Model):
    __tablename__ = 'parking_spot'

    id = db.Column(db.Integer, primary_key=True)
    lot_id  = db.Column(db.Integer, db.ForeignKey('parking_lot.id'),nullable=False)
    status = db.Column(db.String(1),nullable=False,default='A')
    reservations = db.relationship('reservation', backref='spot_rel', cascade="all, delete")
    
    
class reservation(db.Model):
    __tablename__ = 'reservation'

    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'),nullable=False)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user_info.id'),nullable=False)
    Parking_timestamp = db.Column(db.DateTime, default=datetime.utcnow,nullable=False)
    Leaving_timestamp = db.Column(db.DateTime, nullable=True)
    rate_per_unit = db.Column(db.Float,nullable=False,default=10.0)
    total_cost = db.Column(db.Float,nullable=True)
    vehicle_number = db.Column(db.String(20))
    status = db.Column(db.String(20), nullable=False, default='Parked')

    spot = db.relationship('parking_spot', back_populates='reservations')  
    lot = db.relationship('parking_lot', back_populates='reservations', foreign_keys=[lot_id])
    user = db.relationship('user_info', back_populates='reservations')  
       

class contact_message(db.Model):
    __tablename__ = 'contact_message'

    id = db.Column(db.Integer, primary_key=True)
    Full_name = db.Column(db.String,nullable=False)
    email = db.Column(db.String,nullable=False)
    subject = db.Column(db.String,nullable=False)
    message = db.Column(db.String,nullable=False)
    timestamp = db.Column(db.DateTime,default=datetime.utcnow)

