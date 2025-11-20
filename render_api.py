#!/usr/bin/env python3
"""
render_api.py - Render 배포용 Flask API 서버 (Supabase + Kakao OAuth)
- POST /solve: 근무표 생성 요청 처리
- POST /auth/kakao/callback: 카카오 로그인 콜백
- GET /auth/me: 현재 사용자 정보
- POST /rooms: 방 생성
- GET /rooms: 내 방 목록
- GET /rooms/<room_id>: 방 정보
- POST /rooms/<room_id>/join: 방 입장
- POST /rooms/<room_id>/preferences: 희망 근무 제출
- GET /rooms/<room_id>/preferences: 희망 근무 조회
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import sys
import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# fouroff_ver_8 모듈 임포트
sys.path.insert(0, os.path.dirname(__file__))
from fouroff_ver_8 import parse_input, solve_cpsat, validate_result

app = Flask(__name__)
CORS(app)  # CORS 허용

# Supabase 클라이언트 초기화
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
KAKAO_REST_API_KEY = os.environ.get('KAKAO_REST_API_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[WARNING] SUPABASE_URL or SUPABASE_KEY not set. Database features disabled.", file=sys.stderr)
    supabase: Client = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ========================================
# 헬퍼 함수
# ========================================

def get_user_from_token(auth_header):
    """Authorization 헤더에서 사용자 정보 추출"""
    if not supabase or not auth_header:
        return None
    
    try:
        token = auth_header.replace('Bearer ', '')
        user = supabase.auth.get_user(token)
        return user
    except Exception as e:
        print(f"[ERROR] Token validation failed: {e}", file=sys.stderr)
        return None


# ========================================
# Health Check
# ========================================

@app.route('/', methods=['GET'])
def home():
    """Health check 엔드포인트"""
    return jsonify({
        'status': 'ok',
        'message': 'Nurse Schedule API Server with Supabase + Kakao OAuth',
        'version': 'ver_8_auth',
        'supabase': 'enabled' if supabase else 'disabled'
    })


# ========================================
# 인증 (Auth)
# ========================================

@app.route('/auth/kakao/callback', methods=['POST'])
def kakao_callback():
    """카카오 로그인 콜백 처리"""
    if not supabase:
        return jsonify({'status': 'error', 'message': 'Supabase not configured'}), 500
    
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        
        if not access_token:
            return jsonify({'status': 'error', 'message': 'access_token required'}), 400
        
        # Supabase에서 카카오 OAuth 처리
        auth_response = supabase.auth.sign_in_with_oauth({
            'provider': 'kakao',
            'options': {
                'access_token': access_token
            }
        })
        
        return jsonify({
            'status': 'success',
            'session': auth_response.session.dict() if auth_response.session else None,
            'user': auth_response.user.dict() if auth_response.user else None
        }), 200
    
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/auth/me', methods=['GET'])
def get_me():
    """현재 사용자 정보 조회"""
    if not supabase:
        return jsonify({'status': 'error', 'message': 'Supabase not configured'}), 500
    
    auth_header = request.headers.get('Authorization')
    user = get_user_from_token(auth_header)
    
    if not user:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    return jsonify({
        'status': 'success',
        'user': user.user.dict()
    }), 200


# ========================================
# 방 관리 (Rooms)
# ========================================

@app.route('/rooms', methods=['POST'])
def create_room():
    """방 생성"""
    if not supabase:
        return jsonify({'status': 'error', 'message': 'Supabase not configured'}), 500
    
    auth_header = request.headers.get('Authorization')
    user = get_user_from_token(auth_header)
    
    if not user:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        title = data.get('title')
        password = data.get('password')
        
        if not title or not password:
            return jsonify({'status': 'error', 'message': 'title and password required'}), 400
        
        # 방 생성
        room_data = {
            'title': title,
            'password': password,  # 실제로는 해시 처리 필요
            'owner_id': user.user.id,
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('rooms').insert(room_data).execute()
        
        return jsonify({
            'status': 'success',
            'room': result.data[0] if result.data else None
        }), 201
    
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/rooms', methods=['GET'])
def get_rooms():
    """내 방 목록 조회"""
    if not supabase:
        return jsonify({'status': 'error', 'message': 'Supabase not configured'}), 500
    
    auth_header = request.headers.get('Authorization')
    user = get_user_from_token(auth_header)
    
    if not user:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        # 내가 만든 방 목록
        result = supabase.table('rooms').select('*').eq('owner_id', user.user.id).execute()
        
        return jsonify({
            'status': 'success',
            'rooms': result.data
        }), 200
    
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/rooms/<room_id>', methods=['GET'])
def get_room(room_id):
    """방 정보 조회"""
    if not supabase:
        return jsonify({'status': 'error', 'message': 'Supabase not configured'}), 500
    
    auth_header = request.headers.get('Authorization')
    user = get_user_from_token(auth_header)
    
    if not user:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        result = supabase.table('rooms').select('*').eq('id', room_id).execute()
        
        if not result.data:
            return jsonify({'status': 'error', 'message': 'Room not found'}), 404
        
        return jsonify({
            'status': 'success',
            'room': result.data[0]
        }), 200
    
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/rooms/<room_id>/join', methods=['POST'])
def join_room(room_id):
    """방 입장 (비밀번호 확인)"""
    if not supabase:
        return jsonify({'status': 'error', 'message': 'Supabase not configured'}), 500
    
    auth_header = request.headers.get('Authorization')
    user = get_user_from_token(auth_header)
    
    if not user:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        password = data.get('password')
        nurse_name = data.get('nurse_name')
        
        if not password or not nurse_name:
            return jsonify({'status': 'error', 'message': 'password and nurse_name required'}), 400
        
        # 방 존재 및 비밀번호 확인
        room_result = supabase.table('rooms').select('*').eq('id', room_id).execute()
        
        if not room_result.data:
            return jsonify({'status': 'error', 'message': 'Room not found'}), 404
        
        room = room_result.data[0]
        
        if room['password'] != password:
            return jsonify({'status': 'error', 'message': 'Incorrect password'}), 403
        
        # 간호사 이름이 방에 등록되어 있는지 확인 (TODO: nurses 테이블 조회)
        # 현재는 간단히 입장 허용
        
        return jsonify({
            'status': 'success',
            'message': 'Joined successfully',
            'room': room
        }), 200
    
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ========================================
# 희망 근무 (Preferences)
# ========================================

@app.route('/rooms/<room_id>/preferences', methods=['POST'])
def submit_preferences(room_id):
    """희망 근무 제출"""
    if not supabase:
        return jsonify({'status': 'error', 'message': 'Supabase not configured'}), 500
    
    auth_header = request.headers.get('Authorization')
    user = get_user_from_token(auth_header)
    
    if not user:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        nurse_name = data.get('nurse_name')
        schedule = data.get('schedule')  # {day: duty}
        
        if not nurse_name or not schedule:
            return jsonify({'status': 'error', 'message': 'nurse_name and schedule required'}), 400
        
        # 희망 근무 저장
        preference_data = {
            'room_id': room_id,
            'user_id': user.user.id,
            'nurse_name': nurse_name,
            'schedule': schedule,
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('preferences').insert(preference_data).execute()
        
        return jsonify({
            'status': 'success',
            'preference': result.data[0] if result.data else None
        }), 201
    
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/rooms/<room_id>/preferences', methods=['GET'])
def get_preferences(room_id):
    """희망 근무 조회"""
    if not supabase:
        return jsonify({'status': 'error', 'message': 'Supabase not configured'}), 500
    
    auth_header = request.headers.get('Authorization')
    user = get_user_from_token(auth_header)
    
    if not user:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        result = supabase.table('preferences').select('*').eq('room_id', room_id).execute()
        
        return jsonify({
            'status': 'success',
            'preferences': result.data
        }), 200
    
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ========================================
# 근무표 생성 (Solve)
# ========================================

@app.route('/solve', methods=['POST'])
def solve():
    """근무표 생성 요청 처리 (기존 기능 유지)"""
    try:
        # JSON 입력 받기
        input_data = request.get_json()
        
        if not input_data:
            return jsonify({
                'status': 'error',
                'message': 'No JSON data provided'
            }), 400
        
        # JSON 문자열로 변환
        input_json = json.dumps(input_data, ensure_ascii=False)
        
        # 파싱 및 검증
        parsed_data = parse_input(input_json)
        
        # 솔버 실행
        result, solver = solve_cpsat(parsed_data)
        
        # 결과 검증
        validation = validate_result(result, parsed_data)
        
        # 응답 생성
        output = {
            'status': 'success',
            'schedule': result,
            'nurse_wallets': parsed_data['nurse_wallets'],
            'validation': validation,
            'solver_stats': {
                'objective_value': solver.ObjectiveValue(),
                'wall_time': solver.WallTime(),
                'num_branches': solver.NumBranches()
            }
        }
        
        return jsonify(output), 200
    
    except ValueError as e:
        # 입력 검증 실패
        return jsonify({
            'status': 'validation_error',
            'message': str(e)
        }), 400
    
    except RuntimeError as e:
        # 솔버 오류
        return jsonify({
            'status': 'solver_error',
            'message': str(e)
        }), 500
    
    except Exception as e:
        # 기타 오류
        import traceback
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500


if __name__ == '__main__':
    # Render는 PORT 환경변수를 제공
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
