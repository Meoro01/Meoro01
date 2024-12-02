from flask import Flask, render_template, Response
import cv2
import RPi.GPIO as GPIO
import time

app = Flask(__name__)

# 카메라 설정
camera = cv2.VideoCapture(0)  # 0번 카메라 연결

# GPIO 설정
GPIO.setmode(GPIO.BCM)
motor_left_pin = 17
motor_right_pin = 18
GPIO.setup(motor_left_pin, GPIO.OUT)
GPIO.setup(motor_right_pin, GPIO.OUT)

# 모터 제어를 위한 PWM 설정
left_motor_pwm = GPIO.PWM(motor_left_pin, 100)
right_motor_pwm = GPIO.PWM(motor_right_pin, 100)
left_motor_pwm.start(0)
right_motor_pwm.start(0)

# 카메라 스트림 처리 함수
def gen_frames():
    while True:
        success, frame = camera.read()  # 카메라에서 프레임 읽기
        if not success:
            break
        else:
            # 이미지 인코딩 (JPEG로 변환)
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()  # byte 형식으로 변환
            # 스트리밍 형식으로 반환
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# 홈 페이지 라우트 (웹 페이지 렌더링)
@app.route('/')
def index():
    return render_template('index.html')

# 카메라 스트림을 제공하는 라우트
@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# 모터 제어 함수 (속도 조절)
def control_motors(left_speed, right_speed):
    left_motor_pwm.ChangeDutyCycle(left_speed)
    right_motor_pwm.ChangeDutyCycle(right_speed)

# 경로를 따라가며 모터 제어하는 함수
def follow_path(frame):
    # 이미지를 HSV 색 공간으로 변환
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # 검은색 범위 설정
    lower_black = (0, 0, 0)
    upper_black = (180, 255, 50)
    mask = cv2.inRange(hsv, lower_black, upper_black)
    
    # 경로의 크기 분석 (ROI 구분)
    height, width = mask.shape
    left_area = mask[:, :width // 3].sum()
    center_area = mask[:, width // 3: 2 * width // 3].sum()
    right_area = mask[:, 2 * width // 3:].sum()

    # 경로에 따라 모터 속도 조정
    if left_area > center_area and left_area > right_area:
        control_motors(50, 0)  # 좌회전
    elif right_area > center_area and right_area > left_area:
        control_motors(0, 50)  # 우회전
    else:
        control_motors(50, 50)  # 직진

# 서버 실행
if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        camera.release()  # 카메라 종료
        GPIO.cleanup()  # GPIO 설정 해제