# gunicorn_config.py
# Render.com용 Gunicorn 설정

import multiprocessing

# 서버 소켓
bind = "0.0.0.0:10000"

# 워커 설정
workers = 2  # CPU 코어 수 (Render 무료 플랜: 0.5 vCPU → 2개 권장)
worker_class = "sync"
worker_connections = 1000

# Timeout 설정 (가장 중요!)
timeout = 45  # 45초 (기본 30초보다 길게 설정)
graceful_timeout = 30
keepalive = 5

# 로깅
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = "info"

# 재시작
max_requests = 1000
max_requests_jitter = 50

# 보안
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
