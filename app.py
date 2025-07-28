from datetime import date, datetime
from pytz import timezone
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Admin, User, ParkingLot, ParkingSpot, Reservation 
import os
from forms import RegistrationForm, LoginForm
from collections import defaultdict, Counter
from sqlalchemy import func
import json
from flask_migrate import Migrate

app = Flask(__name__, static_folder='static')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'parking.db')
app.config['SECRET_KEY'] = 'secret-key'
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Custom UserLoader for Flask-Login ---

class UnifiedUser(UserMixin):
    def __init__(self, user_id, role):
        self.id = str(user_id)  # Always a string
        self.role = role

    def get_id(self):
        return f"{self.role}:{self.id}"  # Ensures it's stored as 'role:id'


@login_manager.user_loader
def load_user(user_id):
    role, actual_id = user_id.split(':')
    if role == 'admin':
        admin = db.session.get(Admin, int(actual_id))

        if admin:
            return UnifiedUser(f"{admin.id}", 'admin')
    else:
        user = db.session.get(User, int(actual_id))
        if user:
            return UnifiedUser(f"{user.id}", 'user')
    return None

# --- Routes ---

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    error = None

    if form.validate_on_submit():
        login_input = form.login_input.data
        password = form.password.data

        # Try user login with email or full name
        user = User.query.filter(
            (User.email == login_input) | (User.full_name == login_input)
        ).first()

        if user and check_password_hash(user.password, password):
            login_user(UnifiedUser(str(user.id), 'user'))
            session['user_id'] = user.id
            session['role'] = 'user'
            return redirect(url_for('user_dashboard'))

        # Admin login
        admin = Admin.query.filter_by(username=login_input).first()
        if admin and check_password_hash(admin.password, password):
            login_user(UnifiedUser(str(admin.id), 'admin'))
            session['admin_id'] = admin.id
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))

        error = "Invalid username or password"

    return render_template('login.html', form=form, error=error)




@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        full_name = form.full_name.data.strip()
        email = form.email.data.strip().lower()
        password = form.password.data
        confirm_password = form.confirm_password.data

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", form=form)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.", "warning")
            return render_template("register.html", form=form)

        hashed_pw = generate_password_hash(password)
        new_user = User(full_name=full_name, email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for('login'))

    return render_template("register.html", form=form)



@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return "Unauthorized", 403

    bookings = Reservation.query.all()

    # Group by date
    bookings_by_date = defaultdict(int)
    for booking in bookings:
        date_str = booking.parking_time.strftime('%Y-%m-%d')
        bookings_by_date[date_str] += 1

    sorted_dates = sorted(bookings_by_date.items())
    dates = [d for d, _ in sorted_dates]
    counts = [c for _, c in sorted_dates]

    # Count bookings per lot
    lot_bookings = Counter()
    for booking in bookings:
        if booking.spot and booking.spot.lot:
            lot_bookings[booking.spot.lot.location_name] += 1

    lots = list(lot_bookings.keys())
    lot_counts = list(lot_bookings.values())

    # Top users by number of bookings
    user_counts = db.session.query(
        User.full_name, db.func.count(Reservation.id)
    ).join(Reservation).group_by(User.full_name).order_by(db.func.count(Reservation.id).desc()).limit(5).all()

    top_users = [u[0] for u in user_counts]
    user_booking_counts = [u[1] for u in user_counts]

    # Count available vs occupied spots
    from models import ParkingSpot  # if not already imported
    available_count = ParkingSpot.query.filter_by(status='Available').count()
    occupied_count = ParkingSpot.query.filter_by(status='Occupied').count()

    spot_status_data = {
        'labels': ['Available', 'Occupied'],
        'counts': [available_count, occupied_count]
    }

    bookings_data = {
        'dates': dates,
        'counts': counts,
        'top_users': top_users,
        'user_booking_counts': user_booking_counts
    }

    lots_data = {
        'lots': lots,
        'counts': lot_counts
    }

    return render_template("admin_dashboard.html", bookings_data=bookings_data, lots_data=lots_data, spot_status_data=spot_status_data)

@app.route('/admin/add_lot', methods=['GET', 'POST'])
@login_required
def add_parking_lot():
    if current_user.role != 'admin':
        return "Unauthorized", 403

    if request.method == 'POST':
        location = request.form['location']
        address = request.form['address']
        pincode = request.form['pincode']
        price = float(request.form['price'])
        max_spots = int(request.form['max_spots'])

        # Create lot
        lot = ParkingLot(location_name=location, address=address, pin_code=pincode,
                         price_per_hour=price, max_spots=max_spots)
        db.session.add(lot)
        db.session.commit()

        # Create spots
        for i in range(1, max_spots + 1):
            spot = ParkingSpot(
                lot_id=lot.id,
                spot_number=f"S{i}",
                status='A',
                is_available=True
            )   
            db.session.add(spot)

        db.session.commit()
        flash("Parking lot created successfully", "success")
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_parking_lot.html')

@app.route('/admin/lots', methods=['GET', 'POST'])
@login_required
def view_parking_lots():
    if current_user.role != 'admin':
        return "Unauthorized", 403

    if request.method == 'POST':
        lot_id = request.form.get('lot_id')
        lot = ParkingLot.query.get(lot_id)
        if lot:
            lot.status = 'Inactive' if lot.status == 'Active' else 'Active'
            db.session.commit()
            flash(f"Lot '{lot.location_name}' status changed to {lot.status}", 'info')
        return redirect(url_for('view_parking_lots'))

    lots = ParkingLot.query.all()
    return render_template('admin_lots.html', lots=lots)


@app.route('/admin/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
@login_required
def edit_lot(lot_id):
    if current_user.role != 'admin':
        return "Unauthorized", 403
    
    lot = ParkingLot.query.get(lot_id)

    if not lot:
        flash("Parking lot not found.", "danger")
        return redirect(url_for('view_parking_lots'))
    
    print("Rendering edit_lot page for:", lot.location_name)

    if request.method == 'POST':
        lot.location_name = request.form['location']
        lot.address = request.form['address']
        lot.pin_code = request.form['pincode']
        lot.price_per_hour = float(request.form['price'])
        new_spots = int(request.form['max_spots'])
        
        if new_spots < 0:
            flash("Max spots must be a positive number.", "danger")
        else:
            lot.max_spots = new_spots
            db.session.commit()
            flash("Parking lot updated, including max spots.", "success")
            return redirect(url_for('view_parking_lots'))

    return render_template('edit_parking_lot.html', lot=lot)

@app.route('/admin/delete_lot/<int:lot_id>', methods=['POST'])
@login_required
def delete_lot(lot_id):
    if current_user.role != 'admin':
        return "Unauthorized", 403

    lot = ParkingLot.query.get_or_404(lot_id)

    # Ensure all spots are available
    for spot in lot.spots:
        if spot.status == 'O':
            flash("Cannot delete lot: Some spots are occupied", "danger")
            return redirect(url_for('view_parking_lots'))
        if spot.reservation:  
            flash("Cannot delete lot: Spot has reservation history", "danger")
            return redirect(url_for('view_parking_lots'))
        
    db.session.delete(lot)
    db.session.commit()
    flash("Parking lot deleted", "success")
    return redirect(url_for('view_parking_lots'))

@app.route('/admin/add_spots/<int:lot_id>', methods=['POST'])
@login_required
def add_missing_spots(lot_id):
    if current_user.role != 'admin':
        return "Unauthorized", 403

    lot = ParkingLot.query.get_or_404(lot_id)
    current_spot_count = ParkingSpot.query.filter_by(lot_id=lot.id).count()
    missing_spots = lot.max_spots - current_spot_count

    if missing_spots <= 0:
        flash("No missing spots to add. All spots already exist.", "info")
        return redirect(url_for('view_parking_lots'))

    for i in range(1, missing_spots + 1):
        # Generate a unique spot number like S6, S7, ...
        spot_number = f"S{current_spot_count + i}"
        new_spot = ParkingSpot(
            lot_id=lot.id,
            status='A',
            spot_number=spot_number,
            is_available=True
        )
        db.session.add(new_spot)

    db.session.commit()
    flash(f"{missing_spots} missing spot(s) added to {lot.location_name}.", "success")
    return redirect(url_for('view_parking_lots'))


@app.route('/admin/spots', methods=['GET', 'POST'])
@login_required
def manage_spots():
    if current_user.role != 'admin':
        return "Unauthorized", 403

    try:
        # Auto-release expired bookings here
        now = datetime.now(timezone('Asia/Kolkata'))
        expired_bookings = Reservation.query.filter(
            Reservation.status.in_(['Booked', 'O']),
            Reservation.leaving_time < now
        ).all()

        for booking in expired_bookings:
            booking.status = 'Completed'
            booking.spot.is_available = True
            booking.spot.status = 'A' 

        db.session.commit()

        # Then fetch lots/spots as usual
        lots = ParkingLot.query.all()
        selected_lot_id = request.args.get('lot_id')
        selected_status = request.args.get('status')
        #spots = []

        query = ParkingSpot.query
        if selected_lot_id:
            query = query.filter_by(lot_id=selected_lot_id)
        if selected_status:
            query = query.filter_by(status=selected_status)

        spots = query.all()

        return render_template("admin_spots.html", lots=lots, spots=spots, selected_lot_id=selected_lot_id, selected_status=selected_status)

    except Exception as e:
        print("Error in manage_slots:", e)
        return "Internal Server Error", 500 
    

@app.route('/admin/spots/<int:spot_id>/toggle')
@login_required
def toggle_spot_status(spot_id):
    if current_user.role != 'admin':
        return "Unauthorized", 403

    spot = ParkingSpot.query.get_or_404(spot_id)
    current_status = spot.status.strip().upper()

    print("Toggle Requested for Spot ID:", spot.id)
    print("Current Status Before Toggle:", repr(current_status))

    if current_status == 'A':
        spot.status = 'U'
        print("Status changed to: U (Unavailable)")
    elif current_status == 'U':
        spot.status = 'A'
        print("Status changed to: A (Available)")
    elif current_status == 'O':
        print("Cannot toggle: Spot is occupied (O)")
        flash("Spot status cannot be toggled while Occupied", "danger")
        return redirect(url_for('manage_spots'))
    else:
        print("Unrecognized status value")
        flash("Unknown status value", "danger")
        return redirect(url_for('manage_spots'))

    db.session.commit()
    flash("Spot status updated", "success")
    return redirect(url_for('manage_spots'))


@app.route('/admin/users', methods = ['GET', 'POST'])
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    users = User.query.all()
    selected_user = None
    reservations = []

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        if user_id:
            selected_user = User.query.get(int(user_id))
            reservations = Reservation.query.filter_by(user_id=user_id).all()
        else:
            reservations = Reservation.query.all()
    else:
        reservations = Reservation.query.all()

    return render_template('admin_users.html', users=users, reservations=reservations, selected_user=selected_user)


@app.route('/admin/users/<int:user_id>/bookings')
@login_required
def view_user_bookings(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('login'))

    user = User.query.get_or_404(user_id)
    bookings = Reservation.query.filter_by(user_id=user.id).all()

    return render_template('user_bookings.html', user=user, bookings=bookings)


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('login'))

    user = User.query.get_or_404(user_id)

    
    Reservation.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash("User deleted", "info")
    return redirect(url_for('manage_users'))


@app.route('/admin/bookings')
@login_required
def view_all_bookings():
    if current_user.role != 'admin':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    all_reservations = Reservation.query.join(User).join(ParkingSpot).join(ParkingLot).add_columns(
        User.full_name.label('user_name'),
        ParkingSpot.spot_number.label('spot_number'),
        ParkingLot.location_name.label('lot_location'),
        Reservation.vehicle_number,
        Reservation.parking_time,
        Reservation.leaving_time,
        Reservation.cost,
        Reservation.status
    ).all()

    return render_template('admin_bookings.html', bookings=all_reservations)



@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.role != 'user':
        return "Unauthorized", 403

    try:
        user_id = current_user.id
        user = db.session.get(User, user_id)
        #user = User.query.get(user_id)
        reservations = Reservation.query.filter_by(user_id=user_id).all()
        active_booking = Reservation.query.filter_by(user_id=user_id,status='Booked').order_by(Reservation.parking_time.desc()).first()
        

        # Auto-mark expired bookings
        expired_bookings = Reservation.query.filter(
        Reservation.user_id == user_id,
        Reservation.status == 'Booked',
        Reservation.leaving_time < datetime.now(timezone('Asia/Kolkata'))
        ).all()

        for booking in expired_bookings:
            booking.status = 'Completed'
            booking.spot.is_available = True
            booking.spot.status = 'A' 

        db.session.commit()
        
        print("All Bookings:", reservations)
        for r in reservations:
            print(f"Booking ID {r.id} | Status: {r.status} | Start: {r.parking_time} | End: {r.leaving_time}")
        print("System Time Now:", datetime.now())
        print("Active Booking:", active_booking)
        if active_booking:
            print("Status:", active_booking.status)
            print("Start:", active_booking.parking_time)
            print("End:", active_booking.leaving_time)
 
        # Bookings over time
        booking_stats = db.session.query(
        func.date(Reservation.parking_time),
        func.count()
        ).filter_by(user_id=user_id).group_by(func.date(Reservation.parking_time)).all()

        booking_dates = [str(row[0]) for row in booking_stats]
        booking_counts = [row[1] for row in booking_stats]

        # Cost per day
        cost_stats = db.session.query(
        func.date(Reservation.parking_time),
        func.sum(Reservation.cost)
        ).filter_by(user_id=user_id).group_by(func.date(Reservation.parking_time)).all()

        cost_dates = [str(row[0]) for row in cost_stats]
        daily_costs = [float(row[1]) for row in cost_stats]

        # Latest booking
        latest_booking = db.session.query(Reservation).filter_by(user_id=user_id).order_by(Reservation.parking_time.desc()).first()

        return render_template('user_dashboard.html', user=user, reservations=reservations, active_booking=active_booking,
            booking_dates=json.dumps(booking_dates),
            booking_counts=json.dumps(booking_counts),
            cost_dates=json.dumps(cost_dates),
            daily_costs=json.dumps(daily_costs),
            latest_booking=latest_booking
        )
        
    except Exception as e:
        print("Error in user_dashboard:", e)
        return "Internal Server Error in user_dashboard", 500

@app.route('/user/booking_history')
@login_required
def booking_history():
    if current_user.role != 'user':
        return "Unauthorized", 403

    user_id = int(current_user.get_id().split(':')[1])
    reservations = Reservation.query.filter_by(user_id=user_id).all()

    return render_template('booking_history.html', reservations=reservations)


@app.route('/book', methods=['GET', 'POST'])
@login_required
def book_slot():
    if current_user.role != 'user':
        return "Unauthorized", 403

    lots = ParkingLot.query.filter_by(status='Active').all()
    active_lot_ids = [lot.id for lot in lots]
    available_spots = ParkingSpot.query.filter(
        ParkingSpot.is_available == True,
        ParkingSpot.lot_id.in_(active_lot_ids)
    ).all()

    if request.method == 'POST':
        spot_id = request.form.get('spot_id')
        vehicle_number = request.form['vehicle_number']
        # lot_id = int(request.form['lot_id'])  
        raw_start = request.form['start_time'].strip().upper()
        raw_end = request.form['end_time'].strip().upper()

        # Get today's date
        today = date.today()

        try:
            start_time = datetime.strptime(f"{today} {raw_start}", "%Y-%m-%d %I:%M %p")
            end_time = datetime.strptime(f"{today} {raw_end}", "%Y-%m-%d %I:%M %p")
        except ValueError :
            flash("Invalid time format. Please use format like '10:30 AM'", "danger")
            return redirect(url_for('book_slot'))
        
        if end_time <= start_time:
            flash("End time must be after start time.", "warning")
            return redirect(url_for('book_slot'))
        
        spot = db.session.get(ParkingSpot, spot_id)
        lot = db.session.get(ParkingLot, spot.lot_id)

        if lot.status != 'Active':
            flash("This parking lot is currently inactive. Please select another lot.", "danger")
            return redirect(url_for('book_slot'))


        duration_hours = (end_time - start_time).total_seconds() / 3600
        cost = round(duration_hours * lot.price_per_hour, 2) or 0.0
        
        reservation = Reservation(
            user_id=current_user.id,
            spot_id=spot_id,
            vehicle_number=vehicle_number,
            parking_time=start_time,
            leaving_time=end_time,
            cost=cost,
            status='Booked'
        )

        db.session.add(reservation)

        # Mark spot unavailable
        spot = db.session.get(ParkingSpot, spot_id)
        spot.is_available = False
        spot.status = 'O'  # or 'B' for Booked

        db.session.commit()
        if not spot:
            flash("Invalid spot selected.", "danger")
            return redirect(url_for('book_slot'))
        flash("Booking successful!", "success")
        return redirect(url_for('user_dashboard'))

    return render_template('book_slot.html', lots=lots, spots=available_spots)

@app.route('/release/<int:reservation_id>', methods=['POST'])
@login_required
def release_slot(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    
    user_id = int(current_user.get_id().split(':')[1])
    if current_user.role == 'user' and reservation.user_id != user_id:
        flash("Unauthorized", "danger")
        return redirect(url_for('user_dashboard'))

    if reservation.status == 'Completed':
        flash("Already released", "warning")
        return redirect(url_for('user_dashboard'))

    reservation.leaving_time = datetime.now()
    reservation.status = 'Completed'

    # Cost Calculation (in hours)
    duration = (reservation.leaving_time - reservation.parking_time).total_seconds() / 3600
    lot_price = reservation.spot.lot.price_per_hour
    reservation.cost = round(duration * lot_price, 2)

    # Update spot availability
    reservation.spot.is_available = True
    reservation.spot.status = 'A'

    db.session.commit()
    flash(f"Slot released. Total cost: ₹{reservation.cost}", "success")
    return redirect(url_for('user_dashboard'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


@app.route('/api/lots')
@login_required
def api_lots():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    lots = ParkingLot.query.all()
    data = [{
        'id': lot.id,
        'location_name': lot.location_name,
        'address': lot.address,
        'pin_code': lot.pin_code,
        'price': lot.price_per_hour
    } for lot in lots]

    return jsonify({'lots': data})

@app.route('/api/spots')
@login_required
def api_spots():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    lot_id = request.args.get('lot_id')
    status = request.args.get('status')

    query = ParkingSpot.query
    if lot_id:
        query = query.filter_by(lot_id=lot_id)
    if status:
        query = query.filter_by(status=status)

    spots = query.all()
    data = [{
        'id': spot.id,
        'spot_number': spot.spot_number,
        'status': spot.status,
        'lot_id': spot.lot_id
    } for spot in spots]

    return jsonify({'spots': data})

@app.route('/api/reservations')
@login_required
def api_reservations():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    user_id = request.args.get('user_id')
    query = Reservation.query
    if user_id:
        query = query.filter_by(user_id=user_id)

    reservations = query.all()
    data = [{
        'id': res.id,
        'user_id': res.user_id,
        'spot_id': res.spot_id,
        'parking_time': res.parking_time.isoformat(),
        'leaving_time': res.leaving_time.isoformat(),
        'status': res.status
    } for res in reservations]

    return jsonify({'reservations': data})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)



