import os
import sys
from kin import KinClient, TEST_ENVIRONMENT, PROD_ENVIRONMENT
from kin.utils import get_hd_channels, create_channels
from flask import Flask, request, g, jsonify
import psycopg2
import psycopg2.extras
import asyncio
import random
from flask_limiter import Limiter
from flask_httpauth import HTTPTokenAuth
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON
import firebase_admin
from firebase_admin import credentials, auth, messaging
import gunicorn
from flask_ngrok import run_with_ngrok

http_auth = HTTPTokenAuth(scheme='Token')
kin_env = PROD_ENVIRONMENT
app_id = 'V5Ni'
simple_transfer_seed = os.environ.get('simple_transfer_seed')
simple_transfer_public_address = 'GB43PIR5AKNVBVKXACD3HOSJYGLIVXC7GWPRQZFA4YF2DK33KAGQCFAS'
database_url = os.environ.get('DATABASE_URL')

cred = credentials.Certificate("simpletransfer-202fc-firebase-adminsdk-vccth-4247495da1.json")
firebase_admin.initialize_app(cred)
app = Flask(__name__)
limiter = Limiter(
    app,
    key_func=lambda: "",
    default_limits=["250 per day", "250 per hour"]
)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
SSL_mode = 'allow'
db = SQLAlchemy(app)


class User(db.Model):

    __tablename__ = "users"

    uid = db.Column(db.String, primary_key=True, nullable=False)
    username = db.Column(db.String, unique=True, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    fcm_token = db.Column(db.String)
    device_id = db.Column(db.String)
    public_address = db.Column(db.String)
    balance = db.Column(db.Integer, nullable=False)
    transactions = db.Column(JSON, nullable=False)

    def __init__(self, uid, username, email, device_id=None, fcm_token=None,
                 balance=0, transactions=[], public_address=None):
        self.uid = uid
        self.username = username
        self.email = email
        self.fcm_token = fcm_token
        self.device_id = device_id
        self.public_address = public_address
        self.balance = balance
        self.transactions = transactions


def get_database_connection():
    conn = psycopg2.connect(database_url, sslmode='allow')
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    return conn, cur


# Using this to verify authenticated calls where login is required
@http_auth.verify_token
def verify_token(fb_id_token):
    try:
        decoded_token = auth.verify_id_token(fb_id_token)
        g.uid = decoded_token['uid']
    except Exception as e:
        return False
    return True


async def init_kin():
    client = KinClient(kin_env)
    channels = get_hd_channels(simple_transfer_seed, "", 100)
    account = client.kin_account(seed=simple_transfer_seed, channel_secret_keys=channels, app_id=app_id)
    return client, account


@app.route('/get_username', methods=['POST'])
@http_auth.login_required
@limiter.exempt
def get_username():
    conn, cur = get_database_connection()
    try:
        cur.execute(
            """
            SELECT 
                username
            FROM 
                \"users\"
            WHERE
                uid = %s
            """,
            [g.uid]
        )
        username = cur.fetchone()
        return jsonify({'username': username}), 200
    except Exception as e:
        print(e)
        sys.stdout.flush()
        return jsonify(), 500
    finally:
        cur.close()
        conn.close()


@app.route('/random_username', methods=['POST'])
@http_auth.login_required
@limiter.exempt
def random_username():
    conn, cur = get_database_connection()
    try:
        cur.execute(
            """
            SELECT 
                username
            FROM 
                \"users\"
            """
        )
        users = list(cur.fetchall())
        rand_username = random.choice(users)[0].replace("@username.com", "")
        while rand_username == "simpletransfer":
            rand_username = random.choice(users)[0].replace("@username.com", "")
        return jsonify({'username': rand_username}), 200
    except Exception as e:
        print(e)
        sys.stdout.flush()
        return jsonify(), 500
    finally:
        cur.close()
        conn.close()


async def whitelist_async(json):
    conn, cur = get_database_connection()
    client, account = await init_kin()
    try:
        envelope = json['envelope']
        network_id = json['network_id']
        whitelisted_tx = account.whitelist_transaction(
            {
                "envelope": envelope,
                "network_id": network_id
            }
        )
        conn.commit()
        return jsonify({'tx': whitelisted_tx}), 200
    except Exception as e:
        print(e)
        sys.stdout.flush()
        return jsonify(), 500
    finally:
        cur.close()
        conn.close()
        await client.close()


@app.route('/whitelist', methods=['POST'])
@http_auth.login_required
@limiter.exempt
def whitelist():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response = loop.run_until_complete(whitelist_async(request.get_json()))
    return response


@app.route('/public_address', methods=['POST'])
@http_auth.login_required
@limiter.exempt
def public_address():
    conn, cur = get_database_connection()
    try:
        json = request.get_json()
        username = json['username'].lower()
        cur.execute(
            """
            SELECT 
                *
            FROM 
                \"users\"
            WHERE   
                username = %s
            """,
            [username]
        )
        user = cur.fetchone()
        public_address = user['public_address']
        return jsonify({'public_address': public_address}), 200
    except Exception as e:
        print(e)
        sys.stdout.flush()
        return jsonify(), 500
    finally:
        cur.close()
        conn.close()


async def create_account_async(json):
    conn, cur = get_database_connection()
    client, account = await init_kin()
    try:
        device_id = json['device_id']
        public_address = json['public_address']
        cur.execute(
            """
            SELECT 
                *
            FROM 
                \"users\"
            WHERE   
                device_id = %s
            """,
            [device_id]
        )
        user = cur.fetchone()
        fee = await client.get_minimum_fee()
        if user:
            starting_balance = 0
        else:
            starting_balance = 10
        tx_hash = await account.create_account(public_address, starting_balance,
                                               fee=fee, memo_text='account created')
        cur.execute(
            """
            UPDATE \"users\" 
            SET
                public_address = %s,
                device_id = %s
            WHERE
                uid = %s
            """,
            [public_address, device_id, g.uid]
        )
        conn.commit()
        if user:
            return jsonify(), 200
        else:
            return jsonify(), 201
    except Exception as e:
        print(e)
        sys.stdout.flush()
        return jsonify(), 500
    finally:
        cur.close()
        conn.close()
        await client.close()


@app.route('/create_account', methods=['POST'])
@http_auth.login_required
def create_account():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response = loop.run_until_complete(create_account_async(request.get_json()))
    return response


@app.route('/update_fcm_token', methods=['POST'])
@http_auth.login_required
@limiter.exempt
def update_fcm_token():
    conn, cur = get_database_connection()
    try:
        json = request.get_json()
        fcm_token = json['fcm_token']
        cur.execute(
            """
            UPDATE \"users\" 
            SET
                fcm_token = %s
            WHERE   
                uid = %s
            """,
            [fcm_token, g.uid]
        )
        conn.commit()
        return jsonify(), 200
    except Exception as e:
        print(e)
        sys.stdout.flush()
        return jsonify(), 500
    finally:
        cur.close()
        conn.close()


@app.route('/register', methods=['POST'])
@http_auth.login_required
def register():
    conn, cur = get_database_connection()
    try:
        json = request.get_json()
        username = json['username'].lower()
        email = str(auth.get_user(g.uid).email)
        user = User(uid=g.uid, username=username, email=email)
        cur.execute(
            """
            INSERT into \"users\" 
                (uid, username, email, fcm_token, device_id, public_address, balance, transactions)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [user.uid, user.username, user.email, user.fcm_token, user.device_id,
             user.public_address, user.balance, user.transactions]
        )
        conn.commit()
        return jsonify(), 200
    except Exception as e:
        print(e)
        sys.stdout.flush()
        return jsonify(), 500
    finally:
        cur.close()
        conn.close()


@app.route('/notify', methods=['POST'])
@http_auth.login_required
@limiter.exempt
def notify():
    conn, cur = get_database_connection()
    try:
        json = request.get_json()
        username = json['username'].lower()
        amount = json['amount']
        message = json['message']
        type_ = json['type']
        cur.execute(
            """
            SELECT 
                *
            FROM 
                \"users\"
            WHERE   
                uid = %s
            """,
            [g.uid]
        )
        user = cur.fetchone()
        cur.execute(
            """
            SELECT 
                *
            FROM 
                \"users\"
            WHERE   
                username = %s
            """,
            [username]
        )
        recipient = cur.fetchone()
        fcm_token = recipient['fcm_token']
        if type_ == 'pay':
            title = "New Payment"
            body = "@{} paid you {} Kin - {}".format(user['username'], amount, message)
        elif type_ == 'request':
            title = "New Request"
            body = "@{} has requested {} Kin - {}".format(user['username'], amount, message)
        else:
            raise Exception('Wrong notification type')
        message = messaging.Message(
            data={
                'title': title,
                'body': body,
                'type': type_,
                'username': user['username'],
                'message': message,
                'amount': amount,
                'uid': recipient['uid']
            },
            token=fcm_token,
        )
        try:
            response = messaging.send(message)
            return jsonify(), 200
        except Exception as err:
            raise Exception(err)
    except Exception as e:
        print(e)
        sys.stdout.flush()
        return jsonify(), 500
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    app.run()
