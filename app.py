from flask import Flask
from models import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your-secret-key'

db.init_app(app)

# Route imports will go here
# from controllers import auth_controller, dashboard_controller

if __name__ == '__main__':
    app.run(debug=True)
