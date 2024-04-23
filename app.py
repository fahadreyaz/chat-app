import re
from flask import Flask, redirect, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from jinja2.nodes import MarkSafe
from sqlalchemy.exc import IntegrityError
from flask_socketio import SocketIO, join_room, leave_room, socketio

def getPfp(username):
    return f"https://api.dicebear.com/8.x/bottts/svg?seed={username}&scale=80&backgroundType=gradientLinear,solid&backgroundRotation=0,360,10,20,30,40,50,60,70,80,90,100,140,130,120,110,160,150,170,180&baseColor=039be5,1e88e5,3949ab,5e35b1,7cb342,8e24aa,c0ca33,d81b60,e53935,f4511e,fb8c00,fdd835,ffb300,546e7a&eyes=bulging,eva,frame1,frame2,glow,hearts,robocop,round,roundFrame01,roundFrame02,sensor,shade01&face=round01,round02,square01,square02&mouth=bite,diagram,grill01,grill02,smile01,smile02&texture=circuits,dirty01,dirty02,dots,grunge01,grunge02&top=antenna,antennaCrooked,horns,radar&backgroundColor=b6e3f4,c0aede,d1d4f9,ffd5dc,ffdfbf"

db = SQLAlchemy()
app = Flask(__name__)

socketio = SocketIO()
socketio.init_app(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chat.db"
app.secret_key = "hdgsgn76dgbbd68+6788&5"
db.init_app(app)

user_list = {}
room_list = {}

class Users(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, nullable = False)

class Rooms(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String, unique=True, nullable=False)
    creator = db.Column(db.String, nullable=False)

class Messages(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)
    author = db.Column(db.String, nullable=False)
    message = db.Column(db.String, nullable=False)

with app.app_context():
    db.create_all()


def saveMessage(data):
    message = Messages(room_id=session['room_id'], type=data['type'], author=session['username'], message=data['message'])
    db.session.add(message)
    db.session.commit()

def getMessages():
    data = Messages.query.filter_by(room_id=session['room_id'])
    res = ""
    for record in data:
        author = record.author
        message = record.message
        pfp = getPfp(author)
        element = f'''
<div class="message">
<img src="{pfp}" class="pfp" alt="profile">
        <div class="content">
<h4>{author}</h4>
<p>{message}</p>
        </div>
      </div>
        '''
        res += element
    return res

@app.errorhandler(404)
def notFound(error):
    data = {
        "text": "Could not find the page you are looking for"
    }
    return render_template('404.html', data=data)

@app.route('/home/')
@app.route('/')
def home():
    if not 'username' in session:
        return redirect('/login/')
    data = {
        "username": session["username"],
        "pfpUrl": getPfp(session["username"])
    }
    if 'room_id' in session:
        pass
        #return redirect(f"/rooms/{session['room_id']}")
    return render_template('index.html', data=data)

@app.route('/login/')
def login():
    return render_template('login.html')

@app.route('/signup/')
def signup():
    return render_template('signup.html')

@app.route('/logout/')
def logout():
    session.pop("username", None)
    return redirect('/login/')

@app.route('/addUser', methods=['POST'])
def addUser():
    if request.method == "POST":
        username = str(request.form.get('username')).strip()
        password = str(request.form.get('password')).strip()
        usernsmeRegex = re.match(r'^[\w.-]{3,15}$',username)
        passwordRegex = re.match(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&]{8,30}$", password)
        if usernsmeRegex is None:
            return "Invalid username!"
        elif passwordRegex is None:
            return "Password too weak!"
        else:
            try:
                user = Users(username=username, password=password)
                db.session.add(user)
                db.session.commit()
                session["username"] = username
                return "201"
            except IntegrityError:
                return "Username already in use!"

    return redirect('/signup')

@app.route('/loginUser', methods=['POST'])
def loginUser():
    if request.method == "POST":
        username = str(request.form.get("username")).strip()
        password = str(request.form.get("password")).strip()
        print(username, password)
        user = Users.query.filter_by(username=username).first()
        if user is None:
            return "User not found"
        else:
            if password == user.password:
                session['username'] = username
                return '200'
            else:
                return 'Wrong password!'

    return redirect('/login')

@app.route('/createRoom/', methods=['POST'])
def createRoom():
    if request.method == 'POST':
        roomId = str(request.form.get("code"))
        creator = str(request.form.get("creator"))
        try:
            room = Rooms(room_id=roomId, creator=creator)
            db.session.add(room)
            db.session.commit()
            session["room_id"] = roomId
            return "201"
        except IntegrityError:
            return "Room already exists"
        
    return redirect('/home')

@app.route('/joinRoom/', methods=['POST'])
def joinRoom():
    if request.method == 'POST':
        roomId = str(request.form.get("code")).strip()
        room = Rooms.query.filter_by(room_id=roomId).first()
        if room is None:
            return "Room does not exist"
        session["room_id"] = roomId
        return "200"
    return redirect('/home')

@app.route('/rooms/<roomId>/')
def room(roomId):
    if not "username" in session:
        return redirect('/login')
    roomId = str(roomId).strip()
    if roomId in room_list.keys():
        if session["username"] in room_list[roomId]:
            data = {
                'text': 'Already in this room from another instance, reload the page if you think this is a mistake'
            }
            return render_template('404.html', data=data)
    room = Rooms.query.filter_by(room_id=roomId).first()
    if room is None:
        data = {
            "text": f"Room '{roomId}' does not exist"
        }
        return render_template('404.html', data=data)
    session["room_id"] = roomId
    chats = getMessages()
    data = {
        "room_id": roomId,
        "username": session["username"],
        "previousChat": chats
    }
    return render_template('chatroom.html', data=data)

@socketio.on('connect')
def connect():
    room_id = session['room_id']
    username = session['username']
    user_list[request.sid] = username
    if room_id in room_list.keys():
        room_list[room_id].append(username)
    else:
        room_list[room_id] = [username]
    log = {'content': username +' joined the room'}
    data = {
        'type': 'log',
        'message': log['content']
    }
    #saveMessage(data)
    join_room(room_id)
    socketio.emit('log', log, room=room_id)
    print(f"Online in {room_id}: {str(room_list[room_id])}")

@socketio.on('disconnect')
def disconnect():
    username = session['username']
    room_id = session['room_id']
    user_list.pop(request.sid)
    room_list[room_id].remove(username)
    log = {'content': username + ' has left the room'}
    data = {
        'type': 'log',
        'message': log['content']
    }
    #saveMessage(data)
    leave_room(room_id)
    socketio.emit('log', log, room=room_id)
    print(f"Online in {room_id}: {str(room_list[room_id])}")

@socketio.on('message')
def message(data):
    text = str(data).strip()
    if text == "":
        return 0
    data = {
        'pfp': getPfp(session['username']),
        'username': session['username'],
        'message': text
    }
    chat = {
        'type': 'message',
        'message': text
    }
    saveMessage(chat)
    socketio.emit('recieveMessage', data, room=session['room_id'])

@socketio.on('leave')
def leave(data):
    room_id = session['room_id']
    username = session['username']
    leave_room(room)
    user_list.pop(request.sid)
    room_list[room_id].remove(username)
    log = {'content': username+' has left the room'}
    socketio.emit('log', data=log)

socketio.run(app, host='localhost', use_reloader=True)
#app.run(debug=True)
