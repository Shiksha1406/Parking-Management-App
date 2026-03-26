from flask import *
from sqlalchemy.orm import joinedload
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from Models import db
from datetime import datetime
import matplotlib.pyplot as plt
import os
import io
from io import BytesIO
import base64
import math

app=Flask(__name__)
app.secret_key = 'super_secret_key_12345'

#Database configuration 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

from Models import user_info, parking_lot, parking_spot, reservation, contact_message

# #Create the table once
with app.app_context():
    db.create_all()


@app.route('/')          #Default path
def home():
    return render_template('index.html')


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        user = user_info.query.filter_by(email=email).first()
        if user:
            if user.password==password:
                session['user_id'] = user.id
                session['role'] = user.role

                if user.role==0:
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', message='Incorrect Gmail or password')
        else:
            return render_template('login.html', message='Email not found')
    return render_template('login.html')


@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup_page.html')
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        fullname = request.form.get('fullname').strip()
        password = request.form.get('password')
        Address=request.form.get('Address').strip()
        Pincode=request.form.get('Pincode').strip()
        existing_user=user_info.query.filter_by(email=email).first()
        if existing_user:
            return render_template('signup_page.html', message='Email already exists')
        
        new_user=user_info(fullname=fullname,email=email,Address=Address,Pincode=Pincode,role=1)
        new_user.password=password

        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Account Created succesfully")
            return redirect(url_for('login'))       
        except:
            return render_template('signup_page.html', message='Signup not completed')


@app.route('/admin', methods=['GET','POST'])
def admin():
    if request.method == 'GET':
        return render_template('admin.html')
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        user=user_info.query.filter_by(email=email,role=0).first()
        if user:
            if user.password==password:
                session['user_id'] = user.id
                session['role'] = user.role
                return redirect(url_for('admin_dashboard'))
            else:
                return render_template('admin.html', message='Incorrect password')
        return render_template('admin.html', message='Email not found')
    

@app.route('/dashboard',methods=['GET','POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    search_query = request.args.get('query', '')
    user=user_info.query.get(session['user_id'])

    
    if search_query:
        lots = parking_lot.query.options(joinedload(parking_lot.spots)).filter(
        parking_lot.prime_location_name.ilike(f"%{search_query}%") |  
        parking_lot.Pincode.ilike(f"%{search_query}%")
    ).all()
    else:
        lots = parking_lot.query.options(joinedload(parking_lot.spots)).all()
        
    # for lot in lots:
    #     lot.occupied_spots = sum(1 for s in lot.spots if s.status == 'O')
    #     lot.free_spots = sum(1 for s in lot.spots if s.status == 'A')

    reservation_history = reservation.query.options(joinedload(reservation.spot).joinedload(parking_spot.lot)).filter_by(user_id=user.id).all()


    return render_template('dashboard.html',
                           user=user,
                           reservation=reservation_history,
                           parking_lots=lots)


@app.route('/release_form/<int:res_id>', methods=['GET'])
def release_form_page(res_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    res = reservation.query.get(res_id)
    if not res or res.user_id != session['user_id']:
        flash("Invalid reservation.")
        return redirect(url_for('dashboard'))

    now = datetime.utcnow()
    estimated_duration = (now - res.Parking_timestamp).total_seconds() / 3600
    estimated_cost = round(estimated_duration * res.rate_per_unit, 2)

    return render_template('release_form.html', res=res, now=now, estimated_cost=estimated_cost, current_time=now)
  

@app.route('/release', methods=['POST'])
def release_form():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    res_id = request.form.get('res_id')
    res = reservation.query.get(res_id)

    if not res:
        flash("Reservation not found.")
        return redirect(url_for('dashboard'))
    
    if res.status == 'Parked':
        res.status = 'Parked Out'
        res.Leaving_timestamp = datetime.utcnow()
        
        duration = (res.Leaving_timestamp - res.Parking_timestamp).total_seconds() / 3600
        res.total_cost = round(duration * res.rate_per_unit,2)

        spot = parking_spot.query.get(res.spot_id)
        if spot:
            spot.status = 'A'

        db.session.commit()
        flash("Parking lot released successfully.")

    return redirect(url_for('dashboard'))
        

@app.route('/book_parking', methods=['GET', 'POST'])
def book_parking():
    if 'user_id' not in session:
        return render_template('login.html')
    
    user_id = session['user_id']
    if request.method == "GET":
        lot_id=request.args.get('lot_id')
        spot = parking_spot.query.filter_by(lot_id=lot_id, status='A').first()
        if not spot:
            flash("No available spots in this lot.")
            return redirect(url_for('dashboard'))
        return render_template('book_parking.html', spot_id=spot.id, lot_id=lot_id, user_id=user_id)
    elif request.method == "POST":
        lot_id = request.form.get('lot_id')
        spot_id = request.form.get('spot_id')
        vehicle_number = request.form.get('vehicle_number')

        spot = parking_spot.query.get(spot_id)
        if not spot or spot.status != 'A':
            flash("Spot is not available.")
            return redirect(url_for('dashboard'))
        spot.status = 'O'
        new_res = reservation(
            spot_id=spot.id,
            lot_id=lot_id,
            user_id=user_id,
            vehicle_number=vehicle_number,
            Parking_timestamp=datetime.utcnow(),
            rate_per_unit=10.0, 
            status='Parked'
        )
        
        try:
            db.session.add(new_res)
            db.session.commit()
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            return f"Error during booking: {e}", 500
    


@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'user_id' not in session or session.get('role') !=0:
        return redirect(url_for('login'))
    user = user_info.query.get(session['user_id'])
    lots = parking_lot.query.options(joinedload(parking_lot.spots)).all()

    for lot in lots:
        lot.total_spots = len(lot.spots) 
        lot.total_spots = len(lot.spots)
    return render_template('admin_dashboard.html',lots=lots,user=user)

@app.route('/users', methods=['GET', 'POST'])
def users():
    all_users = user_info.query.all()  
    return render_template('users.html', users=all_users)



@app.route('/add_lot', methods=['GET', 'POST'], endpoint='add_lot')
def add_parking_lot():
    if request.method == 'GET':
        return render_template('add_lot.html')
    if request.method == 'POST':
        prime_location_name=request.form.get('prime_location_name')
        price=int(request.form.get('price'))
        Address=request.form.get('Address')
        Pincode=request.form.get('Pincode')
        maximum_number_of_spots=int(request.form.get('maximum_number_of_spots'))
        existing_lot=parking_lot.query.filter_by(prime_location_name=prime_location_name).first()
        if existing_lot:
            return render_template('add_lot.html',message='Lot already exists')
        new_lot=parking_lot(
            prime_location_name=prime_location_name,
            price=int(price),
            Address=Address,
            Pincode=Pincode,
            maximum_number_of_spots=int(maximum_number_of_spots)
        )
        try:
            db.session.add(new_lot)
            db.session.commit()

            for i in range(maximum_number_of_spots):
                spot = parking_spot(lot_id=new_lot.id, status='A')
                db.session.add(spot)

            db.session.commit()
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            print("DB Error:", e) 
            return render_template('add_lot.html', message='Parking Lot not created.')


@app.route('/edit_parking_lot/<int:lot_id>', methods=['GET','POST'])
def edit_parking_lot(lot_id):
    if 'user_id' not in session or session.get('role') != 0:
        flash("Access denied.")
        return redirect(url_for('login'))
    lot = parking_lot.query.get_or_404(lot_id)
    if request.method == 'POST':
        # lot.name = request.form['name']
        # lot.address = request.form['address']
        # lot.pincode = request.form['pincode']
        lot.price = float(request.form['price_per_hour'])
        new_max_spots = int(request.form['max_spots'])
        
        current_spots = parking_spot.query.filter_by(lot_id=lot.id).all()
        current_count = len(current_spots)

        if new_max_spots > current_count:
            for _ in range(new_max_spots - current_count):
                new_spot = parking_spot(lot_id=lot.id, status='A')
                db.session.add(new_spot)
        elif new_max_spots < current_count:
            to_delete = current_count - new_max_spots
            available_spots = [s for s in current_spots if s.status == 'A']
            if len(available_spots) < to_delete:
                flash(f"Cannot reduce to {new_max_spots}. Only {len(available_spots)} spots are free, but {to_delete} need to be removed.")
                return redirect(url_for('edit_parking_lot', lot_id=lot.id))
            for s in available_spots[:to_delete]:
                db.session.delete(s)
        lot.maximum_number_of_spots = new_max_spots

        db.session.commit()
        flash("Parking lot updated successfully.")
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_parking_lot.html', lot=lot)


@app.route('/view_spot/<int:spot_id>', methods=['GET', 'POST'])
def view_spot(spot_id):
    spot = parking_spot.query.get_or_404(spot_id)
    if request.method == 'POST':
        if spot.status == 'O':
            flash("Cannot delete an occupied spot")
            return redirect(url_for('admin_dashboard'))
        active_reservation = reservation.query.filter_by(spot_id=spot.id, status='Parked').first()
        if active_reservation:
            db.session.delete(active_reservation)
        lot = parking_lot.query.get(spot.lot_id)
        if lot and lot.maximum_number_of_spots > 0:
            lot.maximum_number_of_spots -=1
        db.session.delete(spot)
        db.session.commit()
        flash("Parking spot deleted successfully.")
        return redirect(url_for('admin_dashboard'))
    return render_template('view_spot.html', spot=spot)


@app.route('/occupied_spot_details/<int:spot_id>')
def occupied_spot_details(spot_id):
    spot = parking_spot.query.get_or_404(spot_id)
    if spot.status != 'O':
        flash("Spot is not currently occupied.")
        return redirect(url_for('view_spot',spot_id=spot_id))
    reservation_obj = reservation.query.filter_by(spot_id=spot.id, status='Parked').first()
    if not reservation_obj:
        flash("No reservation found for this occupied spot.")
        return redirect(url_for('view_spot', spot_id=spot_id))
    return render_template('occupied_spot_details.html', spot=spot, reservation=reservation_obj)


@app.route('/user_edit_profile', methods=['GET', 'POST'])
def user_edit_profile():
    if 'user_id' not in session:
        flash("You must be logged in to edit your profile.")
        return redirect(url_for('login'))
    user=user_info.query.get(session['user_id'])
    if request.method == 'POST':
        user.fullname = request.form.get('fullname')
        user.email = request.form.get('email')
        user.Address = request.form.get('address')
        user.Pincode = request.form.get('Pincode')
        user.password = request.form.get('password')

        db.session.commit()
        flash("Profile updated successfully.")
        return redirect(url_for('dashboard'))
    return render_template('user_edit_profile.html', user=user)


@app.route('/admin_edit_profile', methods=['GET', 'POST'])
def admin_edit_profile():
    if 'user_id' not in session or session.get('role')!=0:
        flash("Access denied.")
        return redirect(url_for('login'))
    admin=user_info.query.get(session['user_id'])
    if request.method == 'POST':
        admin.fullname = request.form['fullname']
        admin.email = request.form['email']
        admin.Address = request.form['address']
        admin.Pincode = request.form['Pincode']
        if request.form['password']:
            admin.password = request.form['password']

        db.session.commit()
        flash("Admin Profile updated successfully.")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_edit_profile.html', admin=admin)


@app.route('/search_parking')
def search_parking():
    query = request.args.get('query','').strip()

    if not query:
        flash("Please enter a search term.")
        return redirect(url_for('user_dashboard'))
    
    results = parking_lot.query.filter(
        (parking_lot.prime_location_name.ilike(f'%{query}%')) |
        (parking_lot.Pincode.ilike(f'%{query}%'))
    ).all()

    user=user_info.query.get(session['user_id'])
    return render_template('dashboard.html', parking_lots=results, user=user)


@app.route('/admin_summary')
def admin_summary():
    if 'user_id' not in session or session.get('role') != 0:
        flash("Access denied.")
        return redirect(url_for('login'))
    
    user = user_info.query.get(session['user_id'])
    lots = parking_lot.query.all()

    lot_names = []
    lot_revenue = []
    total_available = 0
    total_occupied = 0

    for lot in lots:
        spots = parking_spot.query.filter_by(lot_id=lot.id).all()
        lot_reservations = reservation.query.join(parking_spot).filter(
            parking_spot.lot_id == lot.id,
            reservation.status == 'Parked Out'
        ).all()

        revenue = sum(res.total_cost or 0.0 for res in lot_reservations)
        lot_names.append(lot.prime_location_name)
        lot_revenue.append(revenue)

        total_available += sum(1 for spot in spots if spot.status == 'A')
        total_occupied += sum(1 for spot in spots if spot.status == 'O')
    filtered_data = [
        (name, revenue) for name, revenue in zip(lot_names, lot_revenue)
        if revenue is not None and not (isinstance(revenue, float) and math.isnan(revenue))
    ]

    if filtered_data and any(rev > 0 for _, rev in filtered_data):
        lot_names, lot_revenue = map(list, zip(*filtered_data))
        plt.figure(figsize=(5, 5))
        plt.pie(lot_revenue, labels=lot_names, autopct='%1.1f%%', startangle=140)
        plt.title('Revenue from each Parking Lot')
    else:
        plt.figure(figsize=(5, 5))
        plt.text(0.5, 0.5, 'No valid revenue data', ha='center', va='center')
        plt.axis('off')

    buf1 = BytesIO()
    plt.savefig(buf1, format="png")
    buf1.seek(0)
    img1 = base64.b64encode(buf1.read()).decode('utf-8')
    buf1.close()
    plt.close()
    
    labels = ['Available', 'Occupied']
    counts = [total_available, total_occupied]

    plt.figure(figsize=(5, 4))
    plt.bar(labels, counts, color=['green', 'red'])
    plt.title('Available vs Occupied Spots')
    plt.ylabel('Count')
    buf2 = BytesIO()
    plt.savefig(buf2, format="png")
    buf2.seek(0)
    img2 = base64.b64encode(buf2.read()).decode('utf-8')
    buf2.close()
    plt.close()


    return render_template(
        'admin_summary.html',
        user=user,
        revenue_chart=img1,
        spot_chart=img2
    )

@app.route('/delete_lot<int:lot_id>', methods=['POST']) 
def delete_lot(lot_id):
    if 'user_id' not in session or session.get('role') != 0:
        flash("Access denied.")
        return redirect(url_for('login'))
    lot = parking_lot.query.get_or_404(lot_id)

    occupied_spots = any(spot.status == 'O' for spot in lot.spots)
    if occupied_spots:
        flash("Cannot delete parking lot: one or more spots are occupied.")
        return redirect(url_for('admin_dashboard'))


    for spot in lot.spots:
        reservation.query.filter_by(spot_id=spot.id).delete()
        db.session.delete(spot)

    db.session.delete(lot)
    db.session.commit()
    flash('Parking lot deleted successfully.')
    return redirect(url_for('admin_dashboard'))
    

@app.route('/user_summary')
def user_summary():
    if 'user_id' not in session or session.get('role') != 1:
        flash("Access denied.")
        return redirect(url_for('login'))
    
    user = user_info.query.get(session['user_id'])

    used_spots = reservation.query.filter_by(user_id=user.id, status='Parked Out').all()

    spot_labels = [
        res.spot.lot.prime_location_name
        for res in used_spots
        if res.spot and res.spot.lot and res.spot.lot.prime_location_name
    ]
    label_count = {}
    for label in spot_labels:
        label_count[label] = label_count.get(label, 0) + 1

    labels = list(label_count.keys())
    values = list(label_count.values())

    plt.figure(figsize=(5, 4))
    plt.bar(labels, values, color='skyblue')
    plt.xlabel("Parking Lots")
    plt.ylabel("Times Used")
    plt.title("Summary of Used Parking Spots")

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    chart_data = base64.b64encode(buffer.read()).decode()
    buffer.close()
    plt.close()

    return render_template('user_summary.html', user=user, chart_data=chart_data)

@app.route('/contact_us')
def contact_us():
    return render_template("contact_us.html")

@app.route('/submit_contact', methods=['POST'])
def submit_contact():
    full_name = request.form.get('name')
    email = request.form.get('email')
    subject = request.form.get('subject')
    message = request.form.get('message')

    contact = contact_message(
        Full_name=full_name,
        email=email,
        subject=subject,
        message=message
    )
    db.session.add(contact)
    db.session.commit()

    flash("Thank you for contacting us!")
    return redirect(url_for('contact_us'))


if __name__=="__main__":
    app.run(debug=True)
