from app import app
from models import db, Admin
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()

    # Create default admin
    if not Admin.query.first():
        admin = Admin(username='Deva', password=generate_password_hash('deva2006'))
        db.session.add(admin)
        db.session.commit()
        print("Admin created.")
    else:
        print("Admin already exists.")


