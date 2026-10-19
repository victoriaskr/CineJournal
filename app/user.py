import psycopg
from app import login_manager
from flask_login import UserMixin
from app import app

class User(UserMixin):
    def __init__(self, id_user, username, password, name, birthday, gender, role):
        self.id_user = id_user
        self.username = username
        self.password = password
        self.name = name
        self.birthday = birthday
        self.gender = gender
        self.role = role

    def get_id(self):
        return (self.id_user)
    @staticmethod
    def get_user_by_username(username):
        with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
            cur = con.cursor()
            cur.execute('SELECT id_user, username, password, name, birthday, gender, role FROM UserProfile WHERE username = %s', (username,))
            result = cur.fetchone()
            if result:
                return User(*result)
            return None

@login_manager.user_loader
def load_user(id_user):
    with psycopg.connect(host=app.config['DB_HOST'],
                             user=app.config['DB_USER'],
                             password=app.config['DB_PASSWORD'],
                             dbname=app.config['DB_NAME']) as con:
        cur = con.cursor()
        cur.execute('SELECT id_user, username, password, name, birthday, gender, role FROM UserProfile WHERE id_user = %s', (id_user,))
        result = cur.fetchone()
        if result:
            return User(*result)
        return None