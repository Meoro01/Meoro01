from flask import Flask, Response, render_template
import cv2
import RPi.GPIO as GPIO
import threading
import time

# Flask 앱 생성
app = Flask(__name__)

# GPIO 설정
GPIO.setmode(GPIO.BCM)

# 모터 핀 설정
LEFT_MOTOR_PWM = 17
RIGHT_MOTOR_PWM = 27
LED_LEFT = 5
LED_STRAIGHT = 6
LED_RIGHT = 13

GPIO.setup([LEFT_MOTOR_PWM, RIGHT_MOTOR_PWM, LED_LEFT, LED_STRAIGHT, LED_RIGHT], GPIO.OUT)

# PWM 설정
left_motor_pwm = GPIO.PWM(LEFT_MOTOR_PWM, 100)
right_motor_pwm = GPIO.PWM(RIGHT_MOTOR_PWM, 100)
left_motor_pwm.start(0)
right_motor_pwm.start(0)

# 카메라 설정
camera = cv2.VideoCapture(0)

# 전역 변수
frame = None
lock = threading.Lock()

# 모터 제어 함수
def control_motors(left_speed, right_speed):
    left_motor_pwm.ChangeDutyCycle(left_speed)
    right_motor_pwm.ChangeDutyCycle(right_speed)

# LED 제어 함수
def control_leds(left_on, straight_on, right_on):
    GPIO.output(LED_LEFT, GPIO.HIGH if left_on else GPIO.LOW)
    GPIO.output(LED_STRAIGHT, GPIO.HIGH if straight_on else GPIO.LOW)
    GPIO.output(LED_RIGHT, GPIO.HIGH if right_on else GPIO.LOW)

# 비디오 스트림 처리
def video_stream():
    global frame
    while True:
        ret, img = camera.read()
        if not ret:
            break

        # 이미지 크기 조정 및 ROI 설정
        height, width, _ = img.shape
        roi = img[height // 2 :, :]

        # 그레이스케일 변환 및 이진화
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)

        # 화면을 좌/중앙/우 3개 영역으로 나누기
        region_width = width // 3
        left_area = binary[:, :region_width].sum()
        center_area = binary[:, region_width : 2 * region_width].sum()
        right_area = binary[:, 2 * region_width :].sum()

        # 경로 분석 및 모터/LED 제어
        if left_area > center_area and left_area > right_area:
            control_motors(50, 70)  # 좌회전
            control_leds(True, False, False)
        elif right_area > center_area and right_area > left_area:
            control_motors(70, 50)  # 우회전
            control_leds(False, False, True)
        else:
            control_motors(60, 60)  # 직진
            control_leds(False, True, False)

        # 웹 스트림용 프레임 업데이트
        with lock:
            frame = img

# Flask 비디오 피드 라우트
@app.route("/video_feed")
def video_feed():
    def generate():
        global frame
        while True:
            with lock:
                if frame is None:
                    continue
                ret, buffer = cv2.imencode(".jpg", frame)
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")
    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

# Flask 메인 페이지 라우트
@app.route("/")
def index():
    return render_template("index.html")

# 백그라운드 비디오 처리 스레드 시작
video_thread = threading.Thread(target=video_stream, daemon=True)
video_thread.start()

# Flask 서버 실행
if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        camera.release()
        GPIO.cleanup()