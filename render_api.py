#!/usr/bin/env python3
"""
render_api.py - Render 배포용 Flask API 서버
- POST /solve: 근무표 생성 요청 처리
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import sys
import os

# fouroff_ver_8 모듈 임포트
# (동일 디렉토리에 fouroff_ver_8.py 필요)
sys.path.insert(0, os.path.dirname(__file__))
from fouroff_ver_8 import parse_input, solve_cpsat, validate_result

app = Flask(__name__)
CORS(app)  # CORS 허용 (Flutter 앱에서 접근 가능하도록)


@app.route('/', methods=['GET'])
def home():
    """Health check 엔드포인트"""
    return jsonify({
        'status': 'ok',
        'message': 'Nurse Schedule API Server',
        'version': 'ver_8'
    })


@app.route('/solve', methods=['POST'])
def solve():
    """근무표 생성 요청 처리"""
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
