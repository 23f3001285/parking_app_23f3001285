from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Admin, User, ParkingLot, ParkingSpot, Reservation 
import os
from sqlalchemy import or_ 

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'parking.db')
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/parking.db'
app.config['SECRET_KEY'] = 'secret-key'
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Custom UserLoader for Flask-Login ---
from flask_login import UserMixin

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
    if request.method == 'POST':
        login_input = request.form['username']
        username = request.form['username']
        password = request.form['password']
        print(f"Login attempt: {username}")

        user = User.query.filter((User.email == username) | (User.full_name == username)).first()

        if user and check_password_hash(user.password, password):
            login_user(UnifiedUser(str(user.id), 'user'))
            session['user_id'] = user.id
            session['role'] = 'user'
            print("User login success")
            return redirect(url_for('user_dashboard'))

        # Now check for Admin
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password, password):
            login_user(UnifiedUser(str(admin.id), 'admin'))
            session['admin_id'] = admin.id
            session['role'] = 'admin'
            print("Admin login success")
            return redirect(url_for('admin_dashboard'))

        print("Login failed: Invalid credentials")
        return render_template('login.html', error="Invalid username or password")

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        if User.query.filter_by(email=email).first():
            flash("User already exists", "warning")
            return redirect(url_for('register'))

        new_user = User(full_name=full_name, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return "Unauthorized", 403
    return render_template('admin_dashboard.html')

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
        for _ in range(max_spots):
            spot = ParkingSpot(lot_id=lot.id, status='A')
            db.session.add(spot)

        db.session.commit()
        flash("Parking lot created successfully", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('add_parking_lot.html')

@app.route('/admin/lots')
@login_required
def view_parking_lots():
    if current_user.role != 'admin':
        return "Unauthorized", 403

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

        db.session.commit()
        flash("Parking lot updated.", "info")
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

    db.session.delete(lot)
    db.session.commit()
    flash("Parking lot deleted", "success")
    return redirect(url_for('view_parking_lots'))

@app.route('/admin/spots')
@login_required
def manage_spots():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    
    spots = ParkingSpot.query.all()
    lots = ParkingLot.query.all()
    return render_template('admin_spots.html', lots=lots, spots=spots)  

@app.route('/admin/spots/<int:spot_id>/toggle')
@login_required
def toggle_spot_status(spot_id):
    if current_user.role != 'admin':
        return "Unauthorized", 403

    spot = ParkingSpot.query.get_or_404(spot_id)

    # Toggle between Available (A) and Unavailable (U)
    if spot.status == 'A':
        spot.status = 'U'
    elif spot.status == 'U':
        spot.status = 'A'
    else:
        flash("Spot status cannot be toggled while Occupied", "danger")
        return redirect(url_for('manage_spots'))

    db.session.commit()
    flash("Spot status updated", "success")
    return redirect(url_for('manage_spots'))



@app.route('/admin/users')
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    users = User.query.all()
    reservations = Reservation.query.all()
    return render_template('admin_users.html', users=users, reservations=reservations)


@app.route('/admin/users/<int:user_id>/bookings')
@login_required
def view_user_bookings(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('login'))

    user = User.query.get_or_404(user_id)
    bookings = Reservation.query.filter_by(user_id=user.id).all()

    return render_template('user_bookings.html', user=user, bookings=bookings)


@app.route('/admin/users/<int:user_id>/delete')
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('login'))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted", "info")
    return redirect(url_for('admin_users'))


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
        user_id = int(current_user.get_id().split(':')[1])
        user = db.session.get(User, user_id)
        #user = User.query.get(user_id)
        reservations = Reservation.query.filter_by(user_id=user_id).all()

        return render_template('user_dashboard.html', user=user, reservations=reservations)

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
   # spot = ParkingSpot.query.get(reservations.spot_id)
   # lot = ParkingLot.query.get(spot.lot_id)


    return render_template('booking_history.html', reservations=reservations)


@app.route('/book', methods=['GET', 'POST'])
@login_required
def book_slot():
    if current_user.role != 'user':
        return "Unauthorized", 403

    lots = ParkingLot.query.all()
    available_spots = ParkingSpot.query.filter_by(is_available=True).all()

    if request.method == 'POST':
        spot_id = request.form.get('spot_id')
       #lot_id = request.form.get('lot_id')
       #spot_id = int(request.form['spot_id'])
        lot_id = int(request.form['lot_id'])  # (optional usage)
        start_time = datetime.strptime(request.form['start_time'], "%I:%M %p")
        end_time = datetime.strptime(request.form['end_time'], "%I:%M %p")
        
        spot = db.session.get(ParkingSpot, spot_id)
        lot = db.session.get(ParkingLot, spot.lot_id)

        duration_hours = (end_time - start_time).total_seconds() / 3600
        cost = round(duration_hours * lot.price_per_hour, 2)

        reservation = Reservation(
            user_id=current_user.id,
            spot_id=spot_id,
            parking_time=start_time,
            leaving_time=end_time,
            cost=cost,
            status='Booked'
        )

        db.session.add(reservation)

        # Mark spot unavailable
        spot = db.session.get(ParkingSpot, spot_id)
        spot.is_available = False

        db.session.commit()
        flash("Booking successful!", "success")
        return redirect(url_for('user_dashboard'))

    return render_template('book_slot.html', lots=lots, spots=available_spots)

@app.route('/release/<int:reservation_id>')
@login_required
def release_slot(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)

    if current_user.role == 'user' and reservation.user_id != int(current_user.id.split(':')[1]):
        flash("Unauthorized", "danger")
        return redirect(url_for('user_dashboard'))

    if reservation.status == 'Completed':
        flash("Already released", "warning")
        return redirect(url_for('user_dashboard'))

    reservation.leaving_time = datetime.utcnow()
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
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)



