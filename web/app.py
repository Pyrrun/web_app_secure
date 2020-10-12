from jwt import decode, InvalidTokenError
from jwt import encode
from uuid import uuid4
from flask import Flask,session
from flask import request, Response
from flask import redirect
from flask import render_template
from flask import make_response
import os
from flask_sqlalchemy import SQLAlchemy
import datetime
import requests
import json
from flask import send_file
import hashlib
from functools import wraps
import time
from flask_talisman import Talisman, ALLOW_FROM
from flask_wtf.csrf import CSRFProtect


SESSION_TIME=500
csp = {
    'default-src': [
        '\'self\'',
        '\'unsafe-inline\'',
    ]
}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(32)
app.config['WTF_CSRF_SECRET_KEY'] = os.urandom(32)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.sqlite"
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
csrf.init_app(app)
talisman = Talisman(app, content_security_policy=csp)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.LargeBinary, nullable=False)

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session = db.Column(db.String)
    session_time = db.Column(db.String)
    login = db.Column(db.String)

db.create_all()



INVALIDATE = -1
JWT_SECRET="haha"
JWT_SESSION_TIME=30

def requires_auth(f):
  @wraps(f)
  def decorated(*args, **kwargs):
    session_id = request.cookies.get('session_id')
    if not db.session.query(db.exists().where(Session.session == session_id)).scalar():
      return redirect('/login')
    return f(*args, **kwargs)
  return decorated

@app.route('/')
def index():
  session_id = request.cookies.get('session_id')
  response = redirect("/welcome" if session_id else "/login")
  return response

@app.route('/login')
def login():
  return render_template('login.html')

@app.route('/register', methods=["GET"])
def register():
  return render_template('register.html')

@app.route('/register', methods=["POST"])
def register2():
  login = request.form['login']
  password = request.form['password']
  if not str.isalnum(login) and len(login) < 30:
    return make_response('zly login',401)
  if len(password) < 8 or len(password) > 64 or not any(char.isdigit() for char in password) or not any(char.isupper() for char in password) or not any(char.islower() for char in password):
    return make_response('niepoprawne haslo',401)
  if db.session.query(db.exists().where(User.login == login)).scalar():
    return make_response('użytkownik już istnieje',401)
  salt = os.urandom(32)
  key = hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,100000)
  storage = salt+key
  db.session.add(User(login=login,password=storage))
  db.session.commit()
  return make_response('konto zostało założone',200)

@app.route('/changepasswd', methods=["GET"])
def changepasswd():
  return render_template('changepasswd.html')

@app.route('/changepasswd', methods=["post"])
def changepasswd2():
  login = request.form['login']
  oldpassword = request.form['oldpassword']
  password = request.form['password']
  if not db.session.query(db.exists().where(User.login == login)).scalar():
    return make_response('użytkownik nie istnieje',401)
  key = User.query.filter_by(login=login).first().password
  salt = key[:32]
  new_key = hashlib.pbkdf2_hmac('sha256',oldpassword.encode('utf-8'),salt,100000)
  if not db.session.query(db.exists().where(User.login == login).where(User.password==salt+new_key)).scalar():
    return make_response('niepoprawne haslo',401)
  if len(password) < 8 or len(password) > 64 or not any(char.isdigit() for char in password) or not any(char.isupper() for char in password) or not any(char.islower() for char in password):
    return make_response('niepoprawne haslo',401)
  salt = os.urandom(32)
  key = hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,100000)
  storage = salt+key
  user = User.query.filter_by(login=login).first()
  user.password = storage
  db.session.commit()
  return make_response('hasło zostało zmienione',200)


@app.route('/auth', methods=['POST'])
def auth():
  login = request.form.get('login')
  password = request.form.get('password')
  response = make_response('proceed to login', 303)
  time.sleep(0.2)
  if db.session.query(db.exists().where(User.login == login)).scalar():
    key = User.query.filter_by(login=login).first().password
    salt = key[:32]
    new_key = hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,100000)
    if db.session.query(db.exists().where(User.login == login).where(User.password==salt+new_key)).scalar():
      session_id = str(uuid4())
      db.session.add(Session(session=session_id,login=login))
      db.session.commit()
      response.set_cookie("session_id", session_id, max_age=SESSION_TIME)
      response.headers["Location"] = "/welcome"
      return response
  response.set_cookie("session_id", "INVALIDATE", max_age=INVALIDATE)
  response.headers["Location"] = "/login"
  return response

@app.route('/logout')
@requires_auth
def logout():
  session_id = request.cookies.get('session_id')
  Session.query.filter_by(session=session_id).delete()
  response = redirect("/login")
  response.set_cookie("session_id", "INVALIDATE", max_age=INVALIDATE)
  return response

@app.route('/<user>/status')
@requires_auth
def status(user):
  resp = requests.get('http://jwt:5000/'+user+'/status')
  return json.dumps(resp.text)

@app.route('/welcome')
@requires_auth
def welcome():
  session_id = request.cookies.get('session_id')
  if session_id:
    if db.session.query(db.exists().where(Session.session == session_id)).scalar():
      col=db.session.query(Session).filter_by(session=session_id).first()
      login=col.login
      resp = requests.get('http://jwt:5000/'+login,params={'login':login})
      download_token = create_download_token(login).decode('ascii')
      upload_token = create_upload_token().decode('ascii')
      js = json.loads(resp.text)

      return render_template('layout.html',user=login,publications=js['publications'])
  return redirect("/login")

@app.route('/others',methods=['POST'])
@requires_auth
def others():
  user = request.form.get('user')
  session_id = request.cookies.get('session_id')
  col=db.session.query(Session).filter_by(session=session_id).first()
  login=col.login
  resp = requests.get('http://jwt:5000/'+user,params={'login':login})
  js = json.loads(resp.text)
  return render_template('layoutothers.html',user=user,publications=js['publications'])

@app.route('/listing')
@requires_auth
def listing():
  users = User.query.all()
  return render_template('listing.html',users=users)


@app.route('/upload', methods=['POST'])
@requires_auth
def upload():
  f = request.files.get('file')
  user = request.form.get('user')
  author = request.form.get('author')
  title = request.form.get('title')
  year = request.form.get('year')
  public = request.form.get('public')
  if public != 'yes':
    public = 'no'
  upload_token = create_upload_token()
  s = requests.Session()
  x=s.post('http://jwt:5000/upload',files={'file':(f.filename,f)},params={
  'user':user,
  'token':upload_token,
  'author' : author,
  'title' : title,
  'year' : year,
  'public' : public
  })
  return redirect('/welcome')

@app.route('/download', methods=['POST'])
@requires_auth
def download():
  f = request.form.get('file')
  user = request.form.get('user')
  token = create_download_token(user)
  s = requests.Session()
  x=s.get('http://jwt:5000/'+user+'/'+f,params={
  'token':token}
  )
  contentType = x.headers['content-type']
  resp = Response(x.content, content_type=contentType)
  return resp

@app.route('/downloadref', methods=['POST'])
@requires_auth
def downloadref():
  f = request.form.get('file')
  user = request.form.get('user')
  id = request.form.get('id')
  token = create_download_token(user)
  s = requests.Session()
  x=s.get('http://jwt:5000/'+user+'/'+id+'/'+f,params={
  'token':token}
  )
  contentType = x.headers['content-type']
  resp = Response(x.content, content_type=contentType)
  return resp

@app.route('/uploadref', methods=['POST'])
@requires_auth
def uploadref():
  f = request.files.get('file')
  user = request.form.get('user')
  id = request.form.get('id')
  s = requests.Session()
  x=s.post('http://jwt:5000/'+user+'/'+str(id),files={'file':(f.filename,f)}
  )
  return redirect('/welcome')


@app.route('/delete', methods=['POST'])
@requires_auth
def delete():
  f = request.form.get('resource')
  user = request.form.get('user')
  s = requests.Session()
  x=s.delete('http://jwt:5000/'+user+'/'+f
  )
  return redirect('/welcome')

@app.route('/deleteref', methods=['POST'])
@requires_auth
def deleteref():
  f = request.form.get('resource')
  user = request.form.get('user')
  id = request.form.get('id')
  s = requests.Session()
  x=s.delete('http://jwt:5000/'+user+'/'+id+'/'+f
  )
  return redirect('/welcome')


def create_download_token(user):
  exp = datetime.datetime.utcnow() + datetime.timedelta(seconds=JWT_SESSION_TIME)
  return encode({
  	 "iss":"web",
     "user":user,
  	 "exp":exp},
     JWT_SECRET, "HS256")


def create_upload_token():
  exp = datetime.datetime.utcnow() + datetime.timedelta(seconds=JWT_SESSION_TIME)
  return encode({
  	"iss":"web",
    "exp":exp},
    JWT_SECRET, "HS256")
