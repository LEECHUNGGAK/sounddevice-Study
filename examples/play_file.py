import argparse
import threading
import sounddevice as sd
import soundfile as sf


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument(
    "-l",
    "--list-devices",
    # store_true: 내정값을 True로 명시합니다.
    action="store_true",
    help="음향 기기를 나열합니다",
)
# parse_known_args: 추가한 인자와 추가하지 않은 인자를 튜플로 반환합니다
args, remaining = parser.parse_known_args()
if args.list_devices:
    print(sd.query_devices())
    parser.exit(0)

parser = argparse.ArgumentParser(parents=[parser])
parser.add_argument(
    "filename",
    help="재생할 파일",
)
parser.add_argument(
    "-d",
    "--device",
    help="출력 기기",
)
args = parser.parse_args(remaining)

event = threading.Event()

try:
    data, sample_frequency = sf.read(
        args.filename,
        always_2d=True,
        # 내정값 False: 단일 채널의의 소리 파일을 1차원 배열로 반환합니다.
        # True: 단일 채널의의 소리 파일을 2차원 배열로 반환합니다.
    )

    current_frame = 0

    def callback(outdata, frames, time, status):
        # 이 함수는 outdata를 stream으로 전달해 소리를 재생합니다.

        global current_frame

        if status:
            print(status)
        # 상태 이상이 발생하면 출력합니다.

        chunksize = min(len(data) - current_frame, frames)
        # 샘플링 속도와 데이터의 남은 길이 중 작은 값을 덩어리 크기로 할당합니다.

        outdata[:chunksize] = data[current_frame : current_frame + chunksize]
        # 현재 프레임부터 덩어리 크기만큼의 프레임까지 출력 데이터로 할당합니다.

        if chunksize < frames:
            outdata[chunksize:] = 0
            raise sd.CallbackStop
        # 덩어리 크기만큼 자른 출력 데이터의 크기가 프레임보다 작을 경우,
        # 프레임의 크기와 같아지도록 출력 데이터의 남은 자리를 0으로 채웁니다.

        current_frame += chunksize

    stream = sd.OutputStream(
        device=args.device,
        samplerate=sample_frequency,
        channels=data.shape[1],
        callback=callback,
        finished_callback=event.set,
        # 콜백 함수의 실행을 마치면 대기를 해제합니다.
    )

    with stream:
        # 재생을 마칠 때까지 대기합니다
        event.wait()

except KeyboardInterrupt:
    parser.exit("프로그램을 중단시켰습니다")
# 윈도우에서는 Ctrl + C 키를 입력해도 해당 예외가 제기되지 않습니다.

except Exception as e:
    parser.exit(f"{type(e).__name__}: {str(e)}")
