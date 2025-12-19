# -----------------------------
# Real-Time Text Chat System Backend
# Using Flask + Socket.IO (Improved)
# -----------------------------

from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from markupsafe import escape
import uuid
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# -----------------------------
# Flask App Configuration
# -----------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "default_secret_key")
CORS(app, origins="http://localhost:3000")

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# -----------------------------
# In-memory storage
# -----------------------------
waiting_users = []    # list of dicts: [{sid: ..., interests: [...]}, ...]
rooms = {}            # {room_id: [user1_sid, user2_sid]}

# -----------------------------
# Utility Functions
# -----------------------------
def match_users(user_sid, interests):
    """Try to match the user based on interests."""
    global waiting_users
    for other in waiting_users:
        common = set(interests).intersection(set(other['interests']))
        if common:
            room_id = str(uuid.uuid4())
            rooms[room_id] = [user_sid, other['sid']]
            join_room(room_id, sid=user_sid)
            join_room(room_id, sid=other['sid'])
            waiting_users.remove(other)

            print(f"✅ Matched {user_sid} & {other['sid']} with interests: {common}")
            emit('matched', {'room': room_id, 'common': list(common)}, room=user_sid)
            emit('matched', {'room': room_id, 'common': list(common)}, room=other['sid'])
            return True
    return False

def leave_current_room(user_sid):
    """Remove a user from their current room and notify partner."""
    for room_id, users in list(rooms.items()):
        if user_sid in users:
            other_user = [u for u in users if u != user_sid]
            if other_user:
                emit('partner_left', room=other_user[0])
            leave_room(room_id, sid=user_sid)
            del rooms[room_id]
            break

# -----------------------------
# Socket Events
# -----------------------------
@socketio.on('connect')
def on_connect():
    print(f"🟢 User connected: {request.sid}")
    emit('connected', {'message': 'Connected to the chat server!'})

@socketio.on('disconnect')
def on_disconnect():
    global waiting_users
    print(f"🔴 User disconnected: {request.sid}")
    # Remove from waiting list
    waiting_users = [u for u in waiting_users if u['sid'] != request.sid]
    # Leave room and notify partner
    leave_current_room(request.sid)

@socketio.on('find_partner')
def find_partner(data):
    """Handle finding a new partner."""
    user_sid = request.sid
    interests = data.get('interests', [])

    # Leave old room first
    leave_current_room(user_sid)

    # Try to match immediately
    matched = match_users(user_sid, interests)
    if not matched:
        # No match found → wait
        waiting_users.append({'sid': user_sid, 'interests': interests})
        emit('waiting', {'message': '⏳ Waiting for someone with similar interests...'})

@socketio.on('message')
def handle_message(data):
    room = data.get('room')
    msg = escape(data.get('message', ''))
    if not room:
        return
    emit('new_message', {'message': msg}, room=room, include_self=False)

@socketio.on('typing')
def handle_typing(data):
    room = data.get('room')
    if room in rooms:
        # Notify the other user in the room that someone is typing
        other_user = [u for u in rooms[room] if u != request.sid]
        if other_user:
            emit('typing', room=other_user[0])

@socketio.on('stop_typing')
def handle_stop_typing(data):
    room = data.get('room')
    if room in rooms:
        # Notify the other user that typing stopped
        other_user = [u for u in rooms[room] if u != request.sid]
        if other_user:
            emit('stop_typing', room=other_user[0])


# -----------------------------
# Run the server
# -----------------------------
if __name__ == '__main__':
    print("🚀 Chat server running on http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
