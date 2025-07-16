# app.py - Main Flask Application File

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with reservations
    reservations = db.relationship('Reservation', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prime_location_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    maximum_number_of_spots = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with parking spots
    spots = db.relationship('ParkingSpot', backref='lot', lazy=True, cascade='all, delete-orphan')

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    status = db.Column(db.String(1), default='A')  # 'A' for Available, 'O' for Occupied
    spot_number = db.Column(db.Integer, nullable=False)
    
    # Relationship with reservations
    reservations = db.relationship('Reservation', backref='spot', lazy=True)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parking_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    leaving_timestamp = db.Column(db.DateTime)
    parking_cost = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)

# Helper Functions
def create_admin_user():
    """Create default admin user if it doesn't exist"""
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Default admin user created: username='admin', password='admin123'")

def create_parking_spots(lot_id, max_spots):
    """Create parking spots for a parking lot"""
    for i in range(1, max_spots + 1):
        spot = ParkingSpot(lot_id=lot_id, spot_number=i)
        db.session.add(spot)
    db.session.commit()

def calculate_parking_cost(reservation):
    """Calculate parking cost based on duration and lot price"""
    if reservation.leaving_timestamp:
        duration_hours = (reservation.leaving_timestamp - reservation.parking_timestamp).total_seconds() / 3600
        lot_price = reservation.spot.lot.price
        return round(duration_hours * lot_price, 2)
    return 0

# Routes
@app.route('/')
def index():
    """Home page - redirect to login"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page for both admin and user"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('Login successful!', 'success')
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password!', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return render_template('register.html')
        
        # Create new user
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Admin Routes
@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard"""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied! Admin login required.', 'error')
        return redirect(url_for('login'))
    
    # Get statistics
    total_lots = ParkingLot.query.count()
    total_spots = ParkingSpot.query.count()
    occupied_spots = ParkingSpot.query.filter_by(status='O').count()
    available_spots = total_spots - occupied_spots
    total_users = User.query.filter_by(role='user').count()
    
    # Get all parking lots with spot counts
    lots = ParkingLot.query.all()
    lot_data = []
    for lot in lots:
        occupied_count = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        available_count = lot.maximum_number_of_spots - occupied_count
        lot_data.append({
            'lot': lot,
            'occupied': occupied_count,
            'available': available_count
        })
    
    return render_template('admin_dashboard.html', 
                         total_lots=total_lots,
                         total_spots=total_spots,
                         occupied_spots=occupied_spots,
                         available_spots=available_spots,
                         total_users=total_users,
                         lot_data=lot_data)

@app.route('/admin/parking-lots')
def admin_parking_lots():
    """View all parking lots"""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('login'))
    
    lots = ParkingLot.query.all()
    return render_template('admin_parking_lots.html', lots=lots)

@app.route('/admin/add-lot', methods=['GET', 'POST'])
def add_parking_lot():
    """Add new parking lot"""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        lot = ParkingLot(
            prime_location_name=request.form['location_name'],
            price=float(request.form['price']),
            address=request.form['address'],
            pin_code=request.form['pin_code'],
            maximum_number_of_spots=int(request.form['max_spots'])
        )
        db.session.add(lot)
        db.session.commit()
        
        # Create parking spots for this lot
        create_parking_spots(lot.id, lot.maximum_number_of_spots)
        
        flash('Parking lot created successfully!', 'success')
        return redirect(url_for('admin_parking_lots'))
    
    return render_template('add_parking_lot.html')

@app.route('/admin/edit-lot/<int:lot_id>', methods=['GET', 'POST'])
def edit_parking_lot(lot_id):
    """Edit existing parking lot"""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('login'))
    
    lot = ParkingLot.query.get_or_404(lot_id)
    
    if request.method == 'POST':
        lot.prime_location_name = request.form['location_name']
        lot.price = float(request.form['price'])
        lot.address = request.form['address']
        lot.pin_code = request.form['pin_code']
        
        # Handle spot count changes
        new_max_spots = int(request.form['max_spots'])
        current_spots = ParkingSpot.query.filter_by(lot_id=lot_id).count()
        
        if new_max_spots > current_spots:
            # Add more spots
            for i in range(current_spots + 1, new_max_spots + 1):
                spot = ParkingSpot(lot_id=lot_id, spot_number=i)
                db.session.add(spot)
        elif new_max_spots < current_spots:
            # Remove spots (only if they're available)
            spots_to_remove = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').filter(
                ParkingSpot.spot_number > new_max_spots
            ).all()
            for spot in spots_to_remove:
                db.session.delete(spot)
        
        lot.maximum_number_of_spots = new_max_spots
        db.session.commit()
        
        flash('Parking lot updated successfully!', 'success')
        return redirect(url_for('admin_parking_lots'))
    
    return render_template('edit_parking_lot.html', lot=lot)

@app.route('/admin/delete-lot/<int:lot_id>')
def delete_parking_lot(lot_id):
    """Delete parking lot (only if all spots are empty)"""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('login'))
    
    lot = ParkingLot.query.get_or_404(lot_id)
    
    # Check if any spots are occupied
    occupied_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='O').count()
    if occupied_spots > 0:
        flash('Cannot delete parking lot! Some spots are still occupied.', 'error')
        return redirect(url_for('admin_parking_lots'))
    
    # Delete the lot (spots will be deleted automatically due to cascade)
    db.session.delete(lot)
    db.session.commit()
    
    flash('Parking lot deleted successfully!', 'success')
    return redirect(url_for('admin_parking_lots'))

@app.route('/admin/spot-status/<int:lot_id>')
def view_spot_status(lot_id):
    """View status of all spots in a parking lot"""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('login'))
    
    lot = ParkingLot.query.get_or_404(lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    
    # Get reservation details for occupied spots
    spot_details = []
    for spot in spots:
        if spot.status == 'O':
            reservation = Reservation.query.filter_by(spot_id=spot.id, is_active=True).first()
            spot_details.append({
                'spot': spot,
                'reservation': reservation
            })
        else:
            spot_details.append({
                'spot': spot,
                'reservation': None
            })
    
    return render_template('spot_status.html', lot=lot, spot_details=spot_details)

@app.route('/admin/users')
def admin_users():
    """View all registered users"""
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('login'))
    
    users = User.query.filter_by(role='user').all()
    return render_template('admin_users.html', users=users)

# User Routes
@app.route('/user/dashboard')
def user_dashboard():
    """User dashboard"""
    if 'user_id' not in session or session.get('role') != 'user':
        flash('Access denied! User login required.', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Get user's current active reservation
    current_reservation = Reservation.query.filter_by(user_id=user_id, is_active=True).first()
    
    # Get user's parking history
    reservations = Reservation.query.filter_by(user_id=user_id).order_by(Reservation.parking_timestamp.desc()).all()
    
    # Get available parking lots
    lots = ParkingLot.query.all()
    lot_availability = []
    for lot in lots:
        available_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').count()
        lot_availability.append({
            'lot': lot,
            'available_spots': available_spots
        })
    
    return render_template('user_dashboard.html',
                         current_reservation=current_reservation,
                         reservations=reservations,
                         lot_availability=lot_availability)

@app.route('/user/book-spot', methods=['POST'])
def book_spot():
    """Book a parking spot"""
    if 'user_id' not in session or session.get('role') != 'user':
        flash('Access denied!', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    lot_id = request.form['lot_id']
    
    # Check if user already has an active reservation
    existing_reservation = Reservation.query.filter_by(user_id=user_id, is_active=True).first()
    if existing_reservation:
        flash('You already have an active parking reservation!', 'error')
        return redirect(url_for('user_dashboard'))
    
    # Find first available spot in the lot
    available_spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
    if not available_spot:
        flash('No available spots in this parking lot!', 'error')
        return redirect(url_for('user_dashboard'))
    
    # Create reservation
    reservation = Reservation(
        spot_id=available_spot.id,
        user_id=user_id
    )
    db.session.add(reservation)
    
    # Mark spot as occupied
    available_spot.status = 'O'
    db.session.commit()
    
    flash('Parking spot booked successfully!', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/user/release-spot')
def release_spot():
    """Release/vacate parking spot"""
    if 'user_id' not in session or session.get('role') != 'user':
        flash('Access denied!', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Find active reservation
    reservation = Reservation.query.filter_by(user_id=user_id, is_active=True).first()
    if not reservation:
        flash('No active reservation found!', 'error')
        return redirect(url_for('user_dashboard'))
    
    # Update reservation
    reservation.leaving_timestamp = datetime.utcnow()
    reservation.parking_cost = calculate_parking_cost(reservation)
    reservation.is_active = False
    
    # Mark spot as available
    spot = ParkingSpot.query.get(reservation.spot_id)
    spot.status = 'A'
    
    db.session.commit()
    
    flash(f'Parking spot released! Total cost: ₹{reservation.parking_cost}', 'success')
    return redirect(url_for('user_dashboard'))

# API Routes (Optional)
@app.route('/api/lot-availability')
def api_lot_availability():
    """API to get parking lot availability"""
    lots = ParkingLot.query.all()
    data = []
    for lot in lots:
        available_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').count()
        data.append({
            'id': lot.id,
            'name': lot.prime_location_name,
            'available_spots': available_spots,
            'total_spots': lot.maximum_number_of_spots,
            'price': lot.price
        })
    return jsonify(data)

@app.route('/api/spot-status/<int:spot_id>')
def api_spot_status(spot_id):
    """API to get specific spot status"""
    spot = ParkingSpot.query.get_or_404(spot_id)
    data = {
        'id': spot.id,
        'lot_id': spot.lot_id,
        'spot_number': spot.spot_number,
        'status': 'Available' if spot.status == 'A' else 'Occupied'
    }
    return jsonify(data)

# Initialize database and create tables
def init_db():
    """Initialize database and create default admin"""
    with app.app_context():
        db.create_all()
        create_admin_user()
        print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)