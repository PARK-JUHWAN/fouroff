#!/usr/bin/env python3
# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
"""
render_api.py - Nurse Schedule API Server
Supabase + Kakao OAuth + 로그인 없이 방 생성 지원 + 근무표 저장
Version: ver_8_preference_persistence
"""

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv
import subprocess
from urllib.parse import unquote

load_dotenv()

app = Flask(__name__)
CORS(app)

# Supabase 초기화
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
    """Authorization 헤더에서 사용자 정보 추출"""
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
        "version": "ver_8_preference_persistence"
    }), 200


# ========================================
# Authentication Routes
# ========================================

@app.route('/auth/kakao/callback', methods=['POST'])
def kakao_callback():
    """카카오 로그인 콜백"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        
        if not access_token:
            return jsonify({"error": "Missing access_token"}), 400
        
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
    """현재 사용자 정보"""
    auth_header = request.headers.get('Authorization')
    user = get_user_from_token(auth_header)
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    return jsonify({
        "id": user.id,
        "email": user.email
    }), 200


# ========================================
# Room Routes (로그인 선택사항)
# ========================================

@app.route('/rooms', methods=['OPTIONS'])
def rooms_options():
    """CORS preflight"""
    return '', 200


@app.route('/rooms', methods=['POST'])
def create_room():
    """방 생성 (로그인 필수 아님)"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        title = data.get('title')
        password = data.get('password')
        auth_header = request.headers.get('Authorization')
        
        if not title or not password:
            return jsonify({"error": "Missing title or password"}), 400
        
        user = get_user_from_token(auth_header)
        owner_id = user.id if user else 'anonymous'
        
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
    """방 목록 조회 (로그인 필수 아님)"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
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
    """특정 방 조회"""
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
# Room Update Route
# ========================================

@app.route('/rooms/<room_id>', methods=['PUT'])
def update_room(room_id):
    """방 데이터 업데이트 (근무표 일력 데이터 저장)"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        schedule_data = data.get('schedule_data')
        
        if not schedule_data:
            return jsonify({"error": "Missing schedule_data"}), 400
        
        room_response = supabase.table('rooms').select('id').eq('id', room_id).execute()
        
        if not room_response.data:
            return jsonify({"error": "Room not found"}), 404
        
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
    """방 입장"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        password = data.get('password')
        nurse_name = data.get('nurse_name')
        auth_header = request.headers.get('Authorization')
        
        if not password or not nurse_name:
            return jsonify({"error": "Missing password or nurse_name"}), 400
        
        room_response = supabase.table('rooms').select('*').eq('id', room_id).execute()
        
        if not room_response.data:
            return jsonify({"error": "Room not found"}), 404
        
        room = room_response.data[0]
        if room['password'] != password:
            return jsonify({"error": "Incorrect password"}), 401
        
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
# Preferences Routes (UPDATED for persistence)
# ========================================

@app.route('/rooms/<room_id>/preferences', methods=['POST'])
def submit_preferences(room_id):
    """희망 근무 저장 (UPSERT - 중간저장/제출완료 구분)
    
    Request Body:
        nurse_name: str - 간호사 이름
        schedule: dict - 희망 근무 {day: duty} 형식
        is_submitted: bool - 제출완료 여부 (default: False)
        year: int - 연도
        month: int - 월
    """
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json()
        nurse_name = data.get('nurse_name')
        schedule = data.get('schedule', {})
        is_submitted = data.get('is_submitted', False)
        year = data.get('year')
        month = data.get('month')
        auth_header = request.headers.get('Authorization')
        
        # Validation
        if not nurse_name:
            return jsonify({"error": "Missing nurse_name"}), 400
        
        if not year or not month:
            return jsonify({"error": "Missing year or month"}), 400
        
        # Room verification
        room_response = supabase.table('rooms').select('id').eq('id', room_id).execute()
        
        if not room_response.data:
            return jsonify({"error": "Room not found"}), 404
        
        # User ID extraction
        user = get_user_from_token(auth_header)
        user_id = user.id if user else 'anonymous'
        
        # UPSERT Logic: Check existing preference
        existing = supabase.table('preferences') \
            .select('id') \
            .eq('room_id', room_id) \
            .eq('nurse_name', nurse_name) \
            .eq('year', year) \
            .eq('month', month) \
            .execute()
        
        if existing.data:
            # UPDATE existing record
            pref_response = supabase.table('preferences').update({
                'schedule': schedule,
                'is_submitted': is_submitted,
                'user_id': user_id
            }).eq('id', existing.data[0]['id']).execute()
            
            print(f"[INFO] Updated preference for {nurse_name} in room {room_id} ({year}/{month})")
        else:
            # INSERT new record
            pref_response = supabase.table('preferences').insert({
                'room_id': room_id,
                'user_id': user_id,
                'nurse_name': nurse_name,
                'schedule': schedule,
                'is_submitted': is_submitted,
                'year': year,
                'month': month
            }).execute()
            
            print(f"[INFO] Inserted new preference for {nurse_name} in room {room_id} ({year}/{month})")
        
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


@app.route('/rooms/<room_id>/preferences/clear', methods=['DELETE'])
def clear_preferences(room_id):
    """방의 희망 근무 일괄 삭제 (year/month 변경 시 또는 전체 초기화)
    
    Request Body (optional):
        year: int - 삭제할 연도 (지정 시 해당 year/month만 삭제)
        month: int - 삭제할 월 (지정 시 해당 year/month만 삭제)
    """
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        data = request.get_json() or {}
        year = data.get('year')
        month = data.get('month')
        
        # Build delete query
        query = supabase.table('preferences').delete().eq('room_id', room_id)
        
        # Filter by year/month if specified
        if year and month:
            query = query.eq('year', year).eq('month', month)
            log_msg = f"year={year}, month={month}"
        else:
            log_msg = "all"
        
        response = query.execute()
        
        deleted_count = len(response.data) if response.data else 0
        print(f"[INFO] Cleared {deleted_count} preferences for room {room_id} ({log_msg})")
        
        return jsonify({
            "status": "success",
            "message": "Preferences cleared",
            "deleted_count": deleted_count
        }), 200
    
    except Exception as e:
        print(f"[ERROR] Clear preferences failed: {str(e)}")
        return jsonify({"error": str(e)}), 400


@app.route('/rooms/<room_id>/preferences/<nurse_name>', methods=['GET'])
def get_nurse_preference(room_id, nurse_name):
    """특정 간호사의 희망 근무 조회
    
    Query Parameters:
        year: int (required) - 조회할 연도
        month: int (required) - 조회할 월
    """
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        
        if not year or not month:
            return jsonify({"error": "Missing year or month query params"}), 400
        
        # URL decode nurse_name (handles Korean names)
        decoded_nurse_name = unquote(nurse_name)
        
        response = supabase.table('preferences') \
            .select('*') \
            .eq('room_id', room_id) \
            .eq('nurse_name', decoded_nurse_name) \
            .eq('year', year) \
            .eq('month', month) \
            .execute()
        
        if response.data:
            print(f"[INFO] Found preference for {decoded_nurse_name} in room {room_id} ({year}/{month})")
            return jsonify({
                "status": "success",
                "preference": response.data[0]
            }), 200
        else:
            print(f"[INFO] No preference found for {decoded_nurse_name} in room {room_id} ({year}/{month})")
            return jsonify({
                "status": "success",
                "preference": None
            }), 200
    
    except Exception as e:
        print(f"[ERROR] Get nurse preference failed: {str(e)}")
        return jsonify({"error": str(e)}), 400


@app.route('/rooms/<room_id>/preferences', methods=['GET'])
def get_preferences(room_id):
    """희망 근무 전체 조회 (수간호사용)"""
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
# Schedule Generation (Render 통합)
# ========================================

@app.route('/solve', methods=['POST'])
def solve_schedule():
    """근무표 생성 (fouroff_ver_8.py 호출)"""
    try:
        input_json = request.get_json()
        
        print(f"[DEBUG] /solve called with {len(json.dumps(input_json))} bytes")
        print(f"[DEBUG] Input preview: {json.dumps(input_json, ensure_ascii=False)[:200]}...")
        
        result = subprocess.run(
            ['python3', 'fouroff_ver_8.py', json.dumps(input_json, ensure_ascii=False)],
            capture_output=True,
            text=True,
            timeout=130
        )
        
        if result.returncode != 0:
            print(f"[ERROR] fouroff_ver_8.py exited with code {result.returncode}")
            print(f"[ERROR] stdout: {result.stdout[:1000]}")
            print(f"[ERROR] stderr: {result.stderr[:500]}")
            
            try:
                error_output = json.loads(result.stdout)
                return jsonify(error_output), 400
            except json.JSONDecodeError:
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
