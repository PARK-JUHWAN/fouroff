#!/usr/bin/env python3
# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
"""
render_api.py - Nurse Schedule API Server
Supabase + Kakao OAuth + ë¡œê·¸ì¸ ì—†ì´ ë°© ìƒì„± ì§€ì› + ê·¼ë¬´í‘œ ì €ìž¥
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

# toClaude: KOREAN_PROTECTED - Supabase ì´ˆê¸°í™”
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

# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
def get_user_from_token(auth_header):
    """Authorization í—¤ë”ì—ì„œ ì‚¬ìš©ìž ì •ë³´ ì¶”ì¶œ"""
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

# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
@app.route('/auth/kakao/callback', methods=['POST'])
def kakao_callback():
    """ì¹´ì¹´ì˜¤ ë¡œê·¸ì¸ ì½œë°±"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        
        if not access_token:
            return jsonify({"error": "Missing access_token"}), 400
        
        # toClaude: KOREAN_PROTECTED - Supabaseì—ì„œ ì¹´ì¹´ì˜¤ ì‚¬ìš©ìž ì •ë³´ ê°€ì ¸ì˜¤ê¸°
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


# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
@app.route('/auth/me', methods=['GET'])
def get_current_user():
    """í˜„ìž¬ ì‚¬ìš©ìž ì •ë³´"""
    auth_header = request.headers.get('Authorization')
    user = get_user_from_token(auth_header)
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    return jsonify({
        "id": user.id,
        "email": user.email
    }), 200


# ========================================
# Room Routes (ë¡œê·¸ì¸ ì„ íƒì‚¬í•­)
# ========================================

@app.route('/rooms', methods=['OPTIONS'])
def rooms_options():
    """CORS preflight"""
    return '', 200


# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
@app.route('/rooms', methods=['POST'])
def create_room():
    """ë°© ìƒì„± (ë¡œê·¸ì¸ í•„ìˆ˜ ì•„ë‹˜)"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        title = data.get('title')
        password = data.get('password')
        auth_header = request.headers.get('Authorization')
        
        if not title or not password:
            return jsonify({"error": "Missing title or password"}), 400
        
        # toClaude: KOREAN_PROTECTED - ì‚¬ìš©ìž ID (ë¡œê·¸ì¸í–ˆìœ¼ë©´ ê°€ì ¸ì˜¤ê¸°, ì•„ë‹ˆë©´ anonymous)
        user = get_user_from_token(auth_header)
        owner_id = user.id if user else 'anonymous'
        
        # toClaude: KOREAN_PROTECTED - Supabaseì— ë°© ìƒì„±
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


# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
@app.route('/rooms', methods=['GET'])
def list_rooms():
    """ë°© ëª©ë¡ ì¡°íšŒ (ë¡œê·¸ì¸ í•„ìˆ˜ ì•„ë‹˜)"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        auth_header = request.headers.get('Authorization')
        user = get_user_from_token(auth_header)
        
        # toClaude: KOREAN_PROTECTED - ëª¨ë“  ë°© ì¡°íšŒ (ë¡œê·¸ì¸ ì—¬ë¶€ ë¬´ê´€)
        response = supabase.table('rooms').select('*').execute()
        
        return jsonify({
            "status": "success",
            "rooms": response.data if response.data else []
        }), 200
    
    except Exception as e:
        print(f"[ERROR] List rooms failed: {str(e)}")
        return jsonify({"error": str(e)}), 400


# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
@app.route('/rooms/<room_id>', methods=['GET'])
def get_room(room_id):
    """íŠ¹ì • ë°© ì¡°íšŒ"""
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
# âœ… Room Update Route (NEW!)
# ========================================

# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
@app.route('/rooms/<room_id>', methods=['PUT'])
def update_room(room_id):
    """ë°© ë°ì´í„° ì—…ë°ì´íŠ¸ (ê·¼ë¬´í‘œ ì¼ë ¥ ë°ì´í„° ì €ìž¥)"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        schedule_data = data.get('schedule_data')
        auth_header = request.headers.get('Authorization')
        
        if not schedule_data:
            return jsonify({"error": "Missing schedule_data"}), 400
        
        # toClaude: KOREAN_PROTECTED - ë°© ì¡´ìž¬ í™•ì¸
        room_response = supabase.table('rooms').select('*').eq('id', room_id).execute()
        
        if not room_response.data:
            return jsonify({"error": "Room not found"}), 404
        
        # toClaude: KOREAN_PROTECTED - ë°© ë°ì´í„° ì—…ë°ì´íŠ¸ (schedule_data ì €ìž¥)
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

# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
@app.route('/rooms/<room_id>/join', methods=['POST'])
def join_room(room_id):
    """ë°© ìž…ìž¥"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        password = data.get('password')
        nurse_name = data.get('nurse_name')
        auth_header = request.headers.get('Authorization')
        
        if not password or not nurse_name:
            return jsonify({"error": "Missing password or nurse_name"}), 400
        
        # toClaude: KOREAN_PROTECTED - ë°© í™•ì¸ ë° ë¹„ë°€ë²ˆí˜¸ ê²€ì¦
        room_response = supabase.table('rooms').select('*').eq('id', room_id).execute()
        
        if not room_response.data:
            return jsonify({"error": "Room not found"}), 404
        
        room = room_response.data[0]
        if room['password'] != password:
            return jsonify({"error": "Incorrect password"}), 401
        
        # toClaude: KOREAN_PROTECTED - ì‚¬ìš©ìž ID
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

# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
@app.route('/rooms/<room_id>/preferences', methods=['POST'])
def submit_preferences(room_id):
    """í¬ë§ ê·¼ë¬´ ì œì¶œ"""
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
        
        # toClaude: KOREAN_PROTECTED - ë°© í™•ì¸
        room_response = supabase.table('rooms').select('*').eq('id', room_id).execute()
        
        if not room_response.data:
            return jsonify({"error": "Room not found"}), 404
        
        # toClaude: KOREAN_PROTECTED - ì‚¬ìš©ìž ID
        user = get_user_from_token(auth_header)
        user_id = user.id if user else 'anonymous'
        
        # toClaude: KOREAN_PROTECTED - Preferences ì €ìž¥
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


# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
@app.route('/rooms/<room_id>/preferences', methods=['GET'])
def get_preferences(room_id):
    """í¬ë§ ê·¼ë¬´ ì¡°íšŒ"""
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
# Schedule Generation (Render í†µí•©)
# ========================================

# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
@app.route('/solve', methods=['POST'])
def solve_schedule():
    """ê·¼ë¬´í‘œ ìƒì„± (fouroff_ver_8.py í˜¸ì¶œ)"""
    try:
        input_json = request.get_json()
        
        # toClaude: KOREAN_PROTECTED - âœ… ìž…ë ¥ JSON ë¡œê¹…
        print(f"[DEBUG] /solve called with {len(json.dumps(input_json))} bytes")
        print(f"[DEBUG] Input preview: {json.dumps(input_json, ensure_ascii=False)[:200]}...")
        
        # toClaude: KOREAN_PROTECTED - fouroff_ver_8.py í˜¸ì¶œ
        result = subprocess.run(
            ['python3', 'fouroff_ver_8.py', json.dumps(input_json, ensure_ascii=False)],
            capture_output=True,
            text=True,
            timeout=130  # Gunicorn 30ì´ˆ timeout ëŒ€ì‘
        )
        
        # Always try to parse stdout as JSON (both success and error)
        if result.returncode != 0:
            print(f"[ERROR] fouroff_ver_8.py exited with code {result.returncode}")
            print(f"[ERROR] stdout: {result.stdout[:1000]}")
            print(f"[ERROR] stderr: {result.stderr[:500]}")
            
            # Try to parse stdout as JSON (error info is now in stdout)
            try:
                error_output = json.loads(result.stdout)
                return jsonify(error_output), 400
            except json.JSONDecodeError:
                # If JSON parse fails, return raw output
                return jsonify({
                    "status": "error",
                    "message": result.stderr if result.stderr else result.stdout,
                    "stdout": result.stdout[:1000],
                    "stderr": result.stderr[:500],
                    "returncode": result.returncode
                }), 400
        
        output = json.loads(result.stdout)
        print(f"[DEBUG] fouroff_ver_8.py success: {output.get('status')}")
        return jsonify(output), 200
    
    except subprocess.TimeoutExpired as e:
        print("[ERROR] fouroff_ver_8.py timeout after 130s")
        # Try to get partial output from timeout exception
        if hasattr(e, 'stderr') and e.stderr:
            print(f"[ERROR] Partial stderr: {e.stderr[:500]}")
        if hasattr(e, 'stdout') and e.stdout:
            print(f"[ERROR] Partial stdout: {e.stdout[:500]}")
        return jsonify({
            "status": "error",
            "message": "Timeout: Schedule generation took too long"
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
