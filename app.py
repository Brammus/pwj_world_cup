from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
    UserMixin,
)
from oauthlib.oauth2 import WebApplicationClient
import os
import requests
import json
from flask_sqlalchemy import SQLAlchemy
import psycopg2
from config import config

app = Flask(__name__)

# Configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)

params = config('db.ini')
conn = psycopg2.connect(**params)
user = params.get('user')
password = params.get('password')
host = params.get('host')
database = params.get('database')
DATABASE_URI = f'postgresql://{user}:{password}@{host}/{database}'
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.permanent_session_lifetime = timedelta(minutes=20)
app.secret_key = 'cactus'

db = SQLAlchemy(app)


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


# models
class users(db.Model, UserMixin):
    _id = db.Column("id", db.Integer, primary_key=True)
    email = db.Column(db.String(500))
    name = db.Column(db.String(500))

    def get_id(self):
        return self._id

    def __init__(self, _id, email, name):
        self._id = _id
        self.email = email
        self.name = name


class countries(db.Model):
    _id = db.Column("id", db.Integer, primary_key=True)
    name = db.Column(db.String(500))
    group_id = db.Column(db.Integer)

    def __init__(self, _id, name, group_id):
        self._id = _id
        self.name = name
        self.group_id = group_id


class picks(db.Model):
    _id = db.Column("id", db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    first_seed_id = db.Column(db.Integer)
    second_seed_id = db.Column(db.Integer)

    def __init__(self, _id, user_id, first_seed_id, second_seed_id):
        self._id = _id
        self.user_id = user_id
        self.first_seed_id = first_seed_id
        self.second_seed_id = second_seed_id


class matches(db.Model):
    _id = db.Column("id", db.Integer, primary_key=True)
    match_date = db.Column(db.Date)
    team_1_id = db.Column(db.Integer)
    team_2_id = db.Column(db.Integer)
    team_1_goals = db.Column(db.Integer)
    team_2_goals = db.Column(db.Integer)

    def __init__(self, _id, match_date, team_1_id, team_2_id, team_1_goals, team_2_goals):
        self._id = _id
        self.match_date = match_date
        self.team_1_id = team_1_id
        self.team_2_id = team_2_id
        self.team_1_goals = team_1_goals
        self.team_2_goals = team_2_goals


class groups(db.Model):
    _id = db.Column("id", db.Integer, primary_key=True)
    group_name = db.Column(db.String(500))
    team_1_id = db.Column(db.Integer)
    team_2_id = db.Column(db.Integer)
    team_3_id = db.Column(db.Integer)
    team_4_id = db.Column(db.Integer)

    def __init__(self, _id, group_name, team_1_id, team_2_id, team_3_id, team_4_id):
        self._id = _id
        self.group_name = group_name
        self.team_1_id = team_1_id
        self.team_2_id = team_2_id
        self.team_3_id = team_3_id
        self.team_4_id = team_4_id


login_manager = LoginManager()
login_manager.init_app(app)
client = WebApplicationClient(GOOGLE_CLIENT_ID)


@login_manager.user_loader
def load_user(user_id):
    return users.query.filter_by(_id=user_id).first()


@app.route("/login/callback")
def callback():
    code = request.args.get("code")
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400

    user = users(_id=unique_id, name=users_name, email=users_email)

    # if not users.get(unique_id):
    if not users.query.filter_by(_id=unique_id).first():
        db.session.add(user)
        db.session.commit()
    login_user(user)

    return render_template('index.html')


@app.route("/login")
def login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = client.prepare_request_uri(authorization_endpoint, redirect_uri=request.base_url + "/callback",
                                             scope=["openid", "email", "profile"])
    return redirect(request_uri)


@app.route("/", methods=['POST', 'GET'])
def home():
    if current_user.is_authenticated:
        return render_template('index.html')
    else:
        return '<a class="button" href="/login">Google Login</a>'


if __name__ == "__main__":
    db.create_all()
    app.run(ssl_context="adhoc")
