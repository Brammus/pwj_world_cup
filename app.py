from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session
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
app.permanent_session_lifetime = timedelta(minutes=2000000)
db = SQLAlchemy(app)


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


# models
class users(db.Model, UserMixin):
    _id = db.Column("id", db.String(500), primary_key=True)
    email = db.Column(db.String(500))
    name = db.Column(db.String(500))

    def knockout_points(self):
        points = 0
        all_picks_k = knockout_picks.query.filter_by(user_id=self._id).all()
        for p in all_picks_k:
            knockout_match = knockout_matches.query.filter_by(_id=p.knockout_match_id).first()
            if knockout_match.is_played == True:
                if p.winner == knockout_match.winner:
                    if knockout_match.match_date > datetime(2022, 12, 11).date():
                        points += 2
                    elif knockout_match.match_date > datetime(2022, 12, 15).date():
                        points += 4
                    else:
                        points += 1
        return points

    def calc_points(self):
        # 3 points for 2 correct teams + order
        # 2 points for 2 correct teams + incorrect order
        # 1 point for 1 correct team in any order.
        points = 0
        if len(picks.query.filter_by(user_id=self._id).all()) == 8:
            all_groups = groups.query.all()
            for group in all_groups:
                played = 0
                teams = [group.team_1_id, group.team_2_id, group.team_3_id, group.team_4_id]
                for team in teams:
                    played += group.get_played_by_team(team)
                if played == 12:
                    first_pick = picks.query.filter_by(user_id=self._id, group_id=group._id).first().first_seed_id
                    second_pick = picks.query.filter_by(user_id=self._id, group_id=group._id).first().second_seed_id
                    team_1_points = group.team_1_points
                    team_2_points = group.team_2_points
                    team_3_points = group.team_3_points
                    team_4_points = group.team_4_points
                    team_1_tuple = (group.team_1_id, team_1_points)
                    team_2_tuple = (group.team_2_id, team_2_points)
                    team_3_tuple = (group.team_3_id, team_3_points)
                    team_4_tuple = (group.team_4_id, team_4_points)
                    team_tuples = [team_1_tuple, team_2_tuple, team_3_tuple, team_4_tuple]
                    first_seed_tuple = max(team_tuples, key=lambda item: item[1])
                    first_seed = first_seed_tuple[0]
                    team_tuples.remove(first_seed_tuple)
                    second_seed = max(team_tuples, key=lambda item: item[1])[0]

                    if first_pick == first_seed and second_pick == second_seed:
                        points += 3
                    elif first_pick == second_seed and second_pick == first_seed:
                        points += 2
                    elif first_pick == first_seed or first_pick == second_seed or second_pick == first_seed or second_pick == second_seed:
                        points += 1
        return points

    def has_picks(self):
        has_pick = picks.query.filter_by(user_id=self._id).count()
        return has_pick

    def get_id(self):
        return self._id

    def __init__(self, _id, email, name):
        self._id = _id
        self.email = email
        self.name = name


class knockout_matches(db.Model):
    _id = db.Column("id", db.Integer, primary_key=True)
    team_1_id = db.Column(db.Integer)
    team_2_id = db.Column(db.Integer)
    winner = db.Column(db.Integer)
    is_played = db.Column(db.Boolean)
    match_date = db.Column(db.Date)

    def user_picked(self, user_id):
        if len(knockout_picks.query.filter_by(user_id=user_id, knockout_match_id=self._id).all()):
            return True
        else:
            return False

    def get_pick_by_user(self, user_id):
        return countries.query.filter_by(_id=knockout_picks.query.filter_by(user_id=user_id, knockout_match_id=self._id).first().winner).first().name

    def get_winner_country(self):
        return countries.query.filter_by(_id=self.winner).first().name

    def get_country_1(self):
        return countries.query.filter_by(_id=self.team_1_id).first().name

    def get_country_2(self):
        return countries.query.filter_by(_id=self.team_2_id).first().name

    def __init__(self, team_1_id, team_2_id, winner, is_played, match_date):
        self.team_1_id = team_1_id
        self.team_2_id = team_2_id
        self.winner = winner
        self.is_played = is_played
        self.match_date = match_date


class knockout_picks(db.Model):
    _id = db.Column("id", db.Integer, primary_key=True)
    knockout_match_id = db.Column(db.Integer)
    user_id = db.Column(db.String(500))
    winner = db.Column(db.Integer)

    def __init__(self, knockout_match_id, user_id, winner):
        self.knockout_match_id = knockout_match_id
        self.user_id = user_id
        self.winner = winner
    # def __init__(self, knockout_match_id, user_id, winner):
    #     self.knockout_match_id = knockout_match_id
    #     self.winner = winner
    #     self.user_id = user_id


class countries(db.Model):
    _id = db.Column("id", db.Integer, primary_key=True)
    name = db.Column(db.String(500))
    flag_name = db.Column(db.String(500))

    def __init__(self, _id, name, flag_name):
        self._id = _id
        self.name = name
        self.flag_name = flag_name


class picks(db.Model):
    _id = db.Column("id", db.Integer, primary_key=True)
    user_id = db.Column(db.String(500))
    group_id = db.Column(db.Integer)
    first_seed_id = db.Column(db.Integer)
    second_seed_id = db.Column(db.Integer)

    def country(self, country_id):
        return countries.query.filter_by(_id=country_id).first().name

    def __init__(self, user_id, first_seed_id, second_seed_id, group_id):
        self.user_id = user_id
        self.first_seed_id = first_seed_id
        self.second_seed_id = second_seed_id
        self.group_id = group_id


class matches(db.Model):
    _id = db.Column("id", db.Integer, primary_key=True)
    match_date = db.Column(db.Date)
    team_1_id = db.Column(db.Integer)
    team_2_id = db.Column(db.Integer)
    team_1_goals = db.Column(db.Integer)
    team_2_goals = db.Column(db.Integer)
    is_played = db.Column(db.Boolean)

    def get_winner(self):
        if self.is_played:
            if self.team_1_goals == self.team_2_goals:
                return 'Draw'
            elif self.team_1_goals > self.team_2_goals:
                return self.team_1_id
            elif self.team_2_goals > self.team_1_goals:
                return self.team_2_id

    def get_country(self, team_id):
        return countries.query.filter_by(_id=team_id).first().name

    def __init__(self, match_date, team_1_id, team_2_id, team_1_goals, team_2_goals):
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
    team_1_points = db.Column(db.Integer)
    team_2_points = db.Column(db.Integer)
    team_3_points = db.Column(db.Integer)
    team_4_points = db.Column(db.Integer)

    def get_played_by_team(self, team_id):
        matches_played_1 = len(matches.query.filter_by(team_1_id=team_id, is_played=True).all())
        matches_played_2 = len(matches.query.filter_by(team_2_id=team_id, is_played=True).all())
        return matches_played_2 + matches_played_1

    def get_points_by_team(self, team_id):
        points = 0
        matches_played_1 = matches.query.filter_by(team_1_id=team_id, is_played=True).all()
        matches_played_2 = matches.query.filter_by(team_2_id=team_id, is_played=True).all()
        matches_played = matches_played_1 + matches_played_2
        for match in matches_played:
            if match.get_winner() == 'Draw':
                points = points + 1
            elif match.get_winner() == team_id:
                points = points + 3
        return points

    def user_picked(self, user_id, group_id):
        user_picks = picks.query.filter_by(user_id=user_id, group_id=group_id).first()
        if user_picks:
            return True
        else:
            return None

    def get_first_seed(self, user_id, group_id):
        first_pick = picks.query.filter_by(user_id=user_id, group_id=group_id).first()
        if first_pick:
            return countries.query.filter_by(_id=first_pick.first_seed_id).first()
        else:
            return None

    def get_second_seed(self, user_id, group_id):
        second_pick = picks.query.filter_by(user_id=user_id, group_id=group_id).first()
        if second_pick:
            return countries.query.filter_by(_id=second_pick.second_seed_id).first()
        else:
            return None

    def get_country(self, team_id):
        return countries.query.filter_by(_id=team_id).first().name

    def get_flag(self, team_id):
        return countries.query.filter_by(_id=team_id).first().name.lower()

    def get_username_by_id(self, user_id):
        return users.query.filter_by(_id=user_id).first().name

    def __init__(self, group_name, team_1_id, team_2_id, team_3_id, team_4_id):
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
    session['name'] = users_name
    session['id'] = unique_id
    return redirect(url_for('index'))


@app.route("/login")
def login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = client.prepare_request_uri(authorization_endpoint, redirect_uri=request.base_url + "/callback",
                                             scope=["openid", "email", "profile"])
    return redirect(request_uri)


@app.route("/", methods=['POST', 'GET'])
def index():
    if current_user.is_authenticated:
        user_email = session['name']
        user_picks_2 = len(knockout_picks.query.filter_by(user_id=session['id']).all())
        available_matches = len(knockout_matches.query.all())

        user_list = users.query.filter_by().all()
        user_picks = None
        selected_user = session['id']
        if request.method == "POST":
            selected_user = request.form['user_dropdown']
            user_picks = picks.query.filter_by(user_id=selected_user).all()

        knockout_match_list = knockout_matches.query.all()
        knockout_list = []
        for k in knockout_match_list:
            picked = knockout_picks.query.filter_by(user_id=selected_user, knockout_match_id=k._id).first()
            picked_country = "Not picked yet"
            if picked:
                picked_country = countries.query.filter_by(_id=picked.winner).first().name
            k_tuple = (k, picked_country)
            knockout_list.append(k_tuple)

        user_list_scores = []
        for item in user_list:
            points = item.calc_points()
            points_knockout = item.knockout_points()
            points_total = points_knockout + points
            if points:
                user_tuple = (item.name, points, points_knockout, points_total)
                user_list_scores.append(user_tuple)
        user_list_scores.sort(key=lambda x: x[3], reverse=True)
        knockout_list.sort(key=lambda x: x[0].match_date, reverse=False)
        return render_template('index.html', user_email=user_email, knockout_list=knockout_list,
                               user_picks_2=user_picks_2, user_list=user_list, user_picks=user_picks,
                               selected_user=selected_user, available_matches=available_matches,
                               user_list_scores=user_list_scores)
    else:
        return '<a class="button" href="/login">Google Login</a>'


@app.route("/groups")
def all_groups():
    if current_user.is_authenticated:
        user_email = session['name']
        group_list = groups.query.all()
        return render_template('groups.html', user_email=user_email, group_list=group_list)
    else:
        return '<a class="button" href="/login">Google Login</a>'


@app.route("/knockout_stage", methods=["POST", "GET"])
def knockout_stage():
    if current_user.is_authenticated:
        user_email = session['name']
        country_list = countries.query.all()
        match_list = knockout_matches.query.all()

        if request.method == "POST":
            team_1_id = str(request.form['first_team'])
            team_2_id = str(request.form['second_team'])
            match_date = request.form['match_date']
            winner = 0
            new_match = knockout_matches(team_1_id, team_2_id, winner, False, match_date)
            db.session.add(new_match)
            db.session.commit()
        return render_template('knockout_stage.html', user_email=user_email, country_list=country_list,
                               match_list=match_list)
    else:
        return '<a class="button" href="/login">Google Login</a>'


@app.route("/knockout_pick", methods=["POST", "GET"])
def knockout_pick():
    if current_user.is_authenticated:
        user_email = session['name']
        country_list = countries.query.all()
        date_today = datetime.date(datetime.today())
        match_list = knockout_matches.query.all()
        user_id = session['id']
        if request.method == "POST":
            match_id = int(request.form['match_id'])
            winner = int(request.form['winner'])
            idk = knockout_picks(match_id, user_id, winner)
            db.session.add(idk)
            db.session.commit()
        return render_template('knockout_pick.html', user_email=user_email, country_list=country_list,
                               match_list=match_list, date_today=date_today, user_id=user_id)
    else:
        return '<a class="button" href="/login">Google Login</a>'


@app.route("/matches", methods=['POST', 'GET'])
def all_matches():
    if current_user.is_authenticated:
        if request.method == "POST":
            match_id = request.form['match_id']
            team_1_goals = request.form['team_1_goals']
            team_2_goals = request.form['team_2_goals']
            selected_match = matches.query.filter_by(_id=match_id).first()
            selected_match.is_played = True
            selected_match.team_1_goals = team_1_goals
            selected_match.team_2_goals = team_2_goals
            db.session.commit()
        user_email = session['name']
        selected_user_id = users.query.filter_by(name=user_email).first()._id
        match_list = matches.query.order_by(matches.match_date, matches.is_played).all()
        return render_template('matches.html', user_email=user_email, match_list=match_list,
                               user_id=str(selected_user_id))
    else:
        return '<a class="button" href="/login">Google Login</a>'


@app.route("/picks", methods=["POST", "GET"])
def all_picks():
    if current_user.is_authenticated:
        user_email = session['name']
        user_id = session['id']
        group_list = groups.query.all()
        pick_list = picks.query.filter_by(user_id=user_id).all()
        if request.method == "POST":
            group_id = request.form['group_id']
            first_seed = request.form['first_seed']
            second_seed = request.form['second_seed']
            if first_seed != '' and second_seed != '':
                if first_seed != second_seed:
                    #first_seed_id = countries.query.filter_by(name=first_seed).first()._id
                    #second_seed_id = countries.query.filter_by(name=second_seed).first()._id
                    #if first_seed and second_seed:
                    old_pick = picks.query.filter_by(user_id=user_id, group_id=group_id).first()
                    if old_pick:
                        old_pick.first_seed_id = first_seed
                        old_pick.second_seed_id = second_seed
                    else:
                        new_pick = picks(first_seed_id=first_seed, second_seed_id=second_seed, user_id=user_id, group_id=group_id)
                        db.session.add(new_pick)
                    db.session.commit()
        return render_template('your_pick.html', user_email=user_email, user_id=user_id, pick_list=pick_list, group_list=group_list)
    else:
        return '<a class="button" href="/login">Google Login</a>'


if __name__ == "__main__":
    db.create_all()
    app.run(ssl_context="adhoc")
