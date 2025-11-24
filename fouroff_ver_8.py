#!/usr/bin/env python3
"""
render_api.py - Nurse Schedule API Server
Supabase + Kakao OAuth + Ã«Â¡Å“ÃªÂ·Â¸Ã¬ÂÂ¸ Ã¬â€”â€ Ã¬ÂÂ´ Ã«Â°Â© Ã¬Æ’ÂÃ¬â€žÂ± Ã¬Â§â‚¬Ã¬â€ºÂ + ÃªÂ·Â¼Ã«Â¬Â´Ã­â€˜Å“ Ã¬Â â‚¬Ã¬Å¾Â¥
"""

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv
import subprocess

load_dotenv()

app = Flask(__name__)
CORS(app)

# Supabase Ã¬Â´Ë†ÃªÂ¸Â°Ã­â„¢â€
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
KAKAO_REST_API_KEY = os.environ.get('KAKAO_REST_API_KEY')

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None

print(f"[INFO] Supabase: {'enabled' if supabase else 'disabled'}")


# ========================================
# Helper Functions
# ========================================

def get_user_from_token(auth_header):
    """Authorization Ã­â€”Â¤Ã«Ââ€Ã¬â€”ÂÃ¬â€žÅ“ Ã¬â€šÂ¬Ã¬Å¡Â©Ã¬Å¾Â Ã¬Â â€¢Ã«Â³Â´ Ã¬Â¶â€Ã¬Â¶Å“"""
    if not auth_header or not supabase:
        return None
    
    try:
        token = auth_header.replace('Bearer ', '')
        user = supabase.auth.get_user(token)
        return user
    except Exception as e:
        print(f"[ERROR] Token validation failed: {str(e)}")
        return None


# ========================================
# Routes
# ========================================

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "message": "Nurse Schedule API Server with Supabase + Kakao OAuth",
        "supabase": "enabled" if supabase else "disabled",
        "version": "ver_8_auth_edit"
    }), 200


# ========================================
# Authentication Routes
# ========================================

@app.route('/auth/kakao/callback', methods=['POST'])
def kakao_callback():
    """Ã¬Â¹Â´Ã¬Â¹Â´Ã¬ËœÂ¤ Ã«Â¡Å“ÃªÂ·Â¸Ã¬ÂÂ¸ Ã¬Â½Å“Ã«Â°Â±"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        
        if not access_token:
            return jsonify({"error": "Missing access_token"}), 400
        
        # SupabaseÃ¬â€”ÂÃ¬â€žÅ“ Ã¬Â¹Â´Ã¬Â¹Â´Ã¬ËœÂ¤ Ã¬â€šÂ¬Ã¬Å¡Â©Ã¬Å¾Â Ã¬Â â€¢Ã«Â³Â´ ÃªÂ°â‚¬Ã¬Â Â¸Ã¬ËœÂ¤ÃªÂ¸Â°
        user = supabase.auth.get_user(access_token)
        
        return jsonify({
            "status": "success",
            "session": {
                "access_token": access_token,
                "user": {
                    "id": user.id if user else None,
                    "email": user.email if user else None
                }
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/auth/me', methods=['GET'])
def get_current_user():
    """Ã­Ëœâ€žÃ¬Å¾Â¬ Ã¬â€šÂ¬Ã¬Å¡Â©Ã¬Å¾Â Ã¬Â â€¢Ã«Â³Â´"""
    auth_header = request.headers.get('Authorization')
    user = get_user_from_token(auth_header)
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    return jsonify({
        "id": user.id,
        "email": user.email
    }), 200


# ========================================
# Room Routes (Ã«Â¡Å“ÃªÂ·Â¸Ã¬ÂÂ¸ Ã¬â€žÂ Ã­Æ’ÂÃ¬â€šÂ¬Ã­â€¢Â­)
# ========================================

@app.route('/rooms', methods=['OPTIONS'])
def rooms_options():
    """CORS preflight"""
    return '', 200


@app.route('/rooms', methods=['POST'])
def create_room():
    """Ã«Â°Â© Ã¬Æ’ÂÃ¬â€žÂ± (Ã«Â¡Å“ÃªÂ·Â¸Ã¬ÂÂ¸ Ã­â€¢â€žÃ¬Ë†Ëœ Ã¬â€¢â€žÃ«â€¹Ëœ)"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        title = data.get('title')
        password = data.get('password')
        auth_header = request.headers.get('Authorization')
        
        if not title or not password:
            return jsonify({"error": "Missing title or password"}), 400
        
        # Ã¬â€šÂ¬Ã¬Å¡Â©Ã¬Å¾Â ID (Ã«Â¡Å“ÃªÂ·Â¸Ã¬ÂÂ¸Ã­â€“Ë†Ã¬Å“Â¼Ã«Â©Â´ ÃªÂ°â‚¬Ã¬Â Â¸Ã¬ËœÂ¤ÃªÂ¸Â°, Ã¬â€¢â€žÃ«â€¹Ë†Ã«Â©Â´ anonymous)
        user = get_user_from_token(auth_header)
        owner_id = user.id if user else 'anonymous'
        
        # SupabaseÃ¬â€”Â Ã«Â°Â© Ã¬Æ’ÂÃ¬â€žÂ±
        response = supabase.table('rooms').insert({
            'title': title,
            'password': password,
            'owner_id': owner_id
        }).execute()
        
        if response.data:
            return jsonify({
                "status": "success",
                "room": response.data[0]
            }), 201
        else:
            return jsonify({"error": "Failed to create room"}), 400
    
    except Exception as e:
        print(f"[ERROR] Create room failed: {str(e)}")
        return jsonify({"error": str(e)}), 400


@app.route('/rooms', methods=['GET'])
def list_rooms():
    """Ã«Â°Â© Ã«ÂªÂ©Ã«Â¡Â Ã¬Â¡Â°Ã­Å¡Å’ (Ã«Â¡Å“ÃªÂ·Â¸Ã¬ÂÂ¸ Ã­â€¢â€žÃ¬Ë†Ëœ Ã¬â€¢â€žÃ«â€¹Ëœ)"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        auth_header = request.headers.get('Authorization')
        user = get_user_from_token(auth_header)
        
        # Ã«ÂªÂ¨Ã«â€œÂ  Ã«Â°Â© Ã¬Â¡Â°Ã­Å¡Å’ (Ã«Â¡Å“ÃªÂ·Â¸Ã¬ÂÂ¸ Ã¬â€”Â¬Ã«Â¶â‚¬ Ã«Â¬Â´ÃªÂ´â‚¬)
        response = supabase.table('rooms').select('*').execute()
        
        return jsonify({
            "status": "success",
            "rooms": response.data if response.data else []
        }), 200
    
    except Exception as e:
        print(f"[ERROR] List rooms failed: {str(e)}")
        return jsonify({"error": str(e)}), 400


@app.route('/rooms/<room_id>', methods=['GET'])
def get_room(room_id):
    """Ã­Å Â¹Ã¬Â â€¢ Ã«Â°Â© Ã¬Â¡Â°Ã­Å¡Å’"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        response = supabase.table('rooms').select('*').eq('id', room_id).execute()
        
        if response.data:
            return jsonify({
                "status": "success",
                "room": response.data[0]
            }), 200
        else:
            return jsonify({"error": "Room not found"}), 404
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ========================================
# Ã¢Å“â€¦ Room Update Route (NEW!)
# ========================================

@app.route('/rooms/<room_id>', methods=['PUT'])
def update_room(room_id):
    """Ã«Â°Â© Ã«ÂÂ°Ã¬ÂÂ´Ã­â€žÂ° Ã¬â€”â€¦Ã«ÂÂ°Ã¬ÂÂ´Ã­Å Â¸ (ÃªÂ·Â¼Ã«Â¬Â´Ã­â€˜Å“ Ã¬Å¾â€¦Ã«Â Â¥ Ã«ÂÂ°Ã¬ÂÂ´Ã­â€žÂ° Ã¬Â â‚¬Ã¬Å¾Â¥)"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        schedule_data = data.get('schedule_data')
        auth_header = request.headers.get('Authorization')
        
        if not schedule_data:
            return jsonify({"error": "Missing schedule_data"}), 400
        
        # Ã«Â°Â© Ã¬Â¡Â´Ã¬Å¾Â¬ Ã­â„¢â€¢Ã¬ÂÂ¸
        room_response = supabase.table('rooms').select('*').eq('id', room_id).execute()
        
        if not room_response.data:
            return jsonify({"error": "Room not found"}), 404
        
        # Ã«Â°Â© Ã«ÂÂ°Ã¬ÂÂ´Ã­â€žÂ° Ã¬â€”â€¦Ã«ÂÂ°Ã¬ÂÂ´Ã­Å Â¸ (schedule_data Ã¬Â â‚¬Ã¬Å¾Â¥)
        update_response = supabase.table('rooms').update({
            'schedule_data': schedule_data
        }).eq('id', room_id).execute()
        
        if update_response.data:
            return jsonify({
                "status": "success",
                "message": "Room data updated successfully",
                "room": update_response.data[0]
            }), 200
        else:
            return jsonify({"error": "Failed to update room"}), 400
    
    except Exception as e:
        print(f"[ERROR] Update room failed: {str(e)}")
        return jsonify({"error": str(e)}), 400


# ========================================
# Join Room Routes
# ========================================

@app.route('/rooms/<room_id>/join', methods=['POST'])
def join_room(room_id):
    """Ã«Â°Â© Ã¬Å¾â€¦Ã¬Å¾Â¥"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        password = data.get('password')
        nurse_name = data.get('nurse_name')
        auth_header = request.headers.get('Authorization')
        
        if not password or not nurse_name:
            return jsonify({"error": "Missing password or nurse_name"}), 400
        
        # Ã«Â°Â© Ã­â„¢â€¢Ã¬ÂÂ¸ Ã«Â°Â Ã«Â¹â€žÃ«Â°â‚¬Ã«Â²Ë†Ã­ËœÂ¸ ÃªÂ²â‚¬Ã¬Â¦Â
        room_response = supabase.table('rooms').select('*').eq('id', room_id).execute()
        
        if not room_response.data:
            return jsonify({"error": "Room not found"}), 404
        
        room = room_response.data[0]
        if room['password'] != password:
            return jsonify({"error": "Incorrect password"}), 401
        
        # Ã¬â€šÂ¬Ã¬Å¡Â©Ã¬Å¾Â ID
        user = get_user_from_token(auth_header)
        user_id = user.id if user else 'anonymous'
        
        return jsonify({
            "status": "success",
            "message": "Successfully joined room",
            "room_id": room_id,
            "nurse_name": nurse_name
        }), 200
    
    except Exception as e:
        print(f"[ERROR] Join room failed: {str(e)}")
        return jsonify({"error": str(e)}), 400


# ========================================
# Preferences Routes
# ========================================

@app.route('/rooms/<room_id>/preferences', methods=['POST'])
def submit_preferences(room_id):
    """Ã­ÂÂ¬Ã«Â§Â ÃªÂ·Â¼Ã«Â¬Â´ Ã¬Â Å“Ã¬Â¶Å“"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        nurse_name = data.get('nurse_name')
        schedule = data.get('schedule', {})
        is_draft = data.get('is_draft', False)
        auth_header = request.headers.get('Authorization')
        
        if not nurse_name:
            return jsonify({"error": "Missing nurse_name"}), 400
        
        # Ã«Â°Â© Ã­â„¢â€¢Ã¬ÂÂ¸
        room_response = supabase.table('rooms').select('*').eq('id', room_id).execute()
        
        if not room_response.data:
            return jsonify({"error": "Room not found"}), 404
        
        # Ã¬â€šÂ¬Ã¬Å¡Â©Ã¬Å¾Â ID
        user = get_user_from_token(auth_header)
        user_id = user.id if user else 'anonymous'
        
        # Preferences Ã¬Â â‚¬Ã¬Å¾Â¥
        pref_response = supabase.table('preferences').insert({
            'room_id': room_id,
            'user_id': user_id,
            'nurse_name': nurse_name,
            'schedule': schedule,
            'is_draft': is_draft
        }).execute()
        
        if pref_response.data:
            return jsonify({
                "status": "success",
                "preference": pref_response.data[0]
            }), 201
        else:
            return jsonify({"error": "Failed to save preferences"}), 400
    
    except Exception as e:
        print(f"[ERROR] Submit preferences failed: {str(e)}")
        return jsonify({"error": str(e)}), 400


@app.route('/rooms/<room_id>/preferences', methods=['GET'])
def get_preferences(room_id):
    """Ã­ÂÂ¬Ã«Â§Â ÃªÂ·Â¼Ã«Â¬Â´ Ã¬Â¡Â°Ã­Å¡Å’"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        response = supabase.table('preferences').select('*').eq('room_id', room_id).execute()
        
        return jsonify({
            "status": "success",
            "preferences": response.data if response.data else []
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ========================================
# Schedule Generation (Render Ã­â€ ÂµÃ­â€¢Â©)
# ========================================

@app.route('/solve', methods=['POST'])
def solve_schedule():
    """ÃªÂ·Â¼Ã«Â¬Â´Ã­â€˜Å“ Ã¬Æ’ÂÃ¬â€žÂ± (fouroff_ver_8.py Ã­ËœÂ¸Ã¬Â¶Å“)"""
    try:
        input_json = request.get_json()
        
        # Ã¢Å“â€¦ Ã¬Å¾â€¦Ã«Â Â¥ JSON Ã«Â¡Å“ÃªÂ¹â€¦
        print(f"[DEBUG] /solve called with {len(json.dumps(input_json))} bytes")
        print(f"[DEBUG] Input preview: {json.dumps(input_json, ensure_ascii=False)[:200]}...")
        
        # fouroff_ver_8.py í˜¸ì¶œ
        result = subprocess.run(
            ['python3', 'fouroff_ver_8.py', json.dumps(input_json, ensure_ascii=False)],
            capture_output=True,
            text=True,
            timeout=35  # Gunicorn 30ì´ˆ timeout ëŒ€ì‘
        )
        
        # Ã¢Å“â€¦ Ã¬Æ’ÂÃ¬â€žÂ¸ Ã¬ËœÂ¤Ã«Â¥Ëœ Ã«Â¡Å“ÃªÂ¹â€¦
        if result.returncode != 0:
            print(f"[ERROR] fouroff_ver_8.py exited with code {result.returncode}")
            print(f"[ERROR] stdout: {result.stdout[:500]}")
            print(f"[ERROR] stderr: {result.stderr[:500]}")
            
            return jsonify({
                "status": "error",
                "message": result.stderr,
                "stdout": result.stdout,
                "returncode": result.returncode
            }), 400
        
        output = json.loads(result.stdout)
        print(f"[DEBUG] fouroff_ver_8.py success: {output.get('status')}")
        return jsonify(output), 200
    
    except subprocess.TimeoutExpired:
        print("[ERROR] fouroff_ver_8.py timeout after 35s")
        return jsonify({
            "status": "error",
            "message": "Timeout: ÃªÂ·Â¼Ã«Â¬Â´Ã­â€˜Å“ Ã¬Æ’ÂÃ¬â€žÂ±Ã¬ÂÂ´ Ã«â€žË†Ã«Â¬Â´ Ã¬ËœÂ¤Ã«Å¾Ëœ ÃªÂ±Â¸Ã«Â Â¸Ã¬Å ÂµÃ«â€¹Ë†Ã«â€¹Â¤"
        }), 408
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decode failed: {str(e)}")
        print(f"[ERROR] Raw output: {result.stdout[:500]}")
        return jsonify({
            "status": "error",
            "message": f"JSON parsing error: {str(e)}",
            "raw_output": result.stdout[:500]
        }), 400
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Solve failed with exception:")
        print(error_trace)
        
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": error_trace
        }), 400


# ========================================
# Error Handlers
# ========================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ========================================
# Main
# ========================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
