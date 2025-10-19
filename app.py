import sys
import subprocess
from flask import Flask
from flask_socketio import SocketIO, emit

# 1. Flask 앱 및 SocketIO 초기화
app = Flask(__name__)
# cors_allowed_origins="*" 는 모든 프론트엔드에서의 연결을 허용합니다. (테스트용)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 2. 사용자가 '연결'되었을 때 실행할 함수
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # 요청하신 터미널 첫 화면 문구 전송
    emit('terminal_output', {'data': '(c) T;Dot.  All rights reserved.\n'})
    emit('terminal_output', {'data': 'i❤️PY Render Backend. Ready.\n'})
    emit('terminal_output', {'data': 'impy> '})

# 3. 사용자가 '연결 해제'되었을 때
@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# 4. 프론트엔드에서 'run_code' 이벤트를 보냈을 때 (핵심)
@socketio.on('run_code')
def handle_run_code(json):
    code = json['code']
    
    # ================================================================
    # !!!!!! 치명적인 보안 경고 !!!!!!
    # 이 코드는 사용자가 보낸 문자열을 서버에서 '그대로' 실행합니다.
    # 만약 사용자가 "import os; os.system('rm -rf /')" 를 보낸다면
    # 이 서버가 파괴됩니다.
    #
    # 이것은 '장난감' 수준의 코드입니다. 
    # 절대 이대로 실제 서비스에 사용해선 안 됩니다.
    # (원래는 Docker 같은 격리된 환경에서 실행해야 합니다)
    # ================================================================

    try:
        # 'subprocess.Popen'을 사용하여 실시간으로 출력을 스트리밍합니다.
        # 이것이 'tqdm' (프로그레스 바) 등을 가능하게 하는 핵심입니다.
        process = subprocess.Popen(
            [sys.executable, '-u', '-c', code], # -u 옵션: 버퍼링 없이 즉시 출력
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1 # 라인 단위 버퍼링
        )

        # 1. 표준 출력(stdout) 스트리밍
        for line in process.stdout:
            emit('terminal_output', {'data': line})
            socketio.sleep(0.01) # 다른 작업도 처리할 수 있게 잠시 대기

        # 2. 에러 출력(stderr) 스트리밍
        for line in process.stderr:
            emit('terminal_output', {'data': f'[ERROR] {line}'})
            socketio.sleep(0.01)

        # 3. 프로세스 종료 대기
        process.wait()

    except Exception as e:
        emit('terminal_output', {'data': f'\n[Server Error] {str(e)}\n'})
    
    # 작업이 끝났으므로 프롬프트를 다시 보냅니다.
    emit('terminal_output', {'data': 'impy> '})


# 이 파일(app.py)을 로컬에서 직접 실행할 때 (테스트용)
if __name__ == '__main__':
    socketio.run(app, debug=True, port=5001)