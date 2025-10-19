import sys
import subprocess
import os
from flask import Flask, request
from flask_socketio import SocketIO, emit
import eventlet # gunicorn -k eventlet을 위해 필요

# 1. Flask 앱 및 SocketIO 초기화
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 2. 사용자(sid)별로 실행 중인 프로세스를 저장할 딕셔너리
user_processes = {}

# 3. input()을 가로채는 파이썬 코드 (수정 없음)
hack_script = """
import sys
import os

# 1. 원래의 input 함수를 백업
__original_input = input

# 2. 새로운 '가짜' input 함수 정의
def __custom_input(prompt=""):
    # 3. 프롬프트(예: '이름: ')를 터미널로 보냄
    sys.stdout.write(prompt)
    sys.stdout.flush()
    
    # 4. "지금 입력 필요!"라는 비밀 신호를 보냄
    sys.stdout.write("__INPUT_REQUEST__\\n")
    sys.stdout.flush()
    
    # 5. 서버로부터 진짜 입력을 받을 때까지 대기
    response = sys.stdin.readline()
    
    # 6. 받은 입력을 반환 (게임 코드는 자기가 입력받은 줄 앎)
    return response.rstrip('\\n')

# 7. 파이썬의 내장 input 함수를 우리가 만든 가짜 함수로 덮어쓰기
__builtins__.input = __custom_input
"""

# 8. 백그라운드에서 터미널 출력을 실시간으로 스트리밍하는 함수 (수정 없음)
def stream_output(process, sid):
    try:
        # 1. 표준 출력(stdout) 스트리밍
        for line in process.stdout:
            if "__INPUT_REQUEST__\n" in line:
                prompt_text = line.replace("__INPUT_REQUEST__\n", "")
                if prompt_text:
                    socketio.emit('terminal_output', {'data': prompt_text}, to=sid)
                socketio.emit('input_request', to=sid) # '입력 요청' 신호 전송
            else:
                socketio.emit('terminal_output', {'data': line}, to=sid)
            socketio.sleep(0.01)

        # 2. 에러 출력(stderr) 스트리밍
        for line in process.stderr:
            socketio.emit('terminal_output', {'data': f'[ERROR] {line}'}, to=sid)
            socketio.sleep(0.01)

    except Exception as e:
        socketio.emit('terminal_output', {'data': f'\n[Stream Error] {e}\n'}, to=sid)
    finally:
        # 3. 프로세스가 끝나면 정리
        process.wait()
        user_processes.pop(sid, None) 
        socketio.emit('terminal_output', {'data': 'impy> '}, to=sid) # 프롬프트 전송


# 9. 사용자가 '연결'되었을 때 (수정 없음)
@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f"Client connected: {sid}")
    emit('terminal_output', {'data': '(c) T;Dot.  All rights reserved.\n'})
    emit('terminal_output', {'data': 'i❤️PY Backend (input() enabled). Ready.\n'})
    emit('terminal_output', {'data': 'impy> '}) 

# 10. 사용자가 '연결 해제'되었을 때 (수정 없음)
@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    process = user_processes.pop(sid, None)
    if process:
        process.kill()
    print(f"Client disconnected: {sid}")

# 11. (신규) 사용자가 팝업창에 '입력'했을 때
@socketio.on('user_input')
def handle_user_input(json_data):
    sid = request.sid
    process = user_processes.get(sid)
    data = json_data['data']

    if process and process.poll() is None: 
        try:
            # ★★★ (핵심 수정) ★★★
            # .encode('utf-8')를 삭제했습니다.
            # 'text=True' 모드이므로 'str'을 그대로 전달해야 합니다.
            process.stdin.write(f"{data}\n")
            process.stdin.flush()
        except Exception as e:
            emit('terminal_output', {'data': f'\n[Input Error] {str(e)}\n'})
    else:
        emit('terminal_output', {'data': '\n[ERROR] No active process.\n'})


# 12. 프론트엔드에서 'run_code' 이벤트를 보냈을 때 (수정 없음)
@socketio.on('run_code')
def handle_run_code(json_data):
    sid = request.sid
    
    old_process = user_processes.pop(sid, None)
    if old_process:
        old_process.kill()
        
    code = json_data['code']
    full_code = hack_script + "\n" + code

    # (보안 경고는 여전히 유효합니다)
    
    try:
        process = subprocess.Popen(
            [sys.executable, '-u', '-c', full_code],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, # ★★★ 바로 이 옵션 때문에 str을 보내야 합니다.
            encoding='utf-8',
            bufsize=1
        )
        
        user_processes[sid] = process
        
        socketio.start_background_task(
            target=stream_output, 
            process=process, 
            sid=sid
        )

    except Exception as e:
        emit('terminal_output', {'data': f'\n[Server Error] {str(e)}\n'})
        emit('terminal_output', {'data': 'impy> '})
