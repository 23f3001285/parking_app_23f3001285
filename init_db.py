from app import app
from models import db, Admin
from werkzeug.security import generate_password_hash

with app.app_context():
    db.drop_all()
    db.create_all()

    # Create default admin
    if not Admin.query.first():
        admin = Admin(username='admin', password=generate_password_hash('admin123'))
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin created and DB initialized.")
    else:
        print("⚠️ Admin already exists.")
