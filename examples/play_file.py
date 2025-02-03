import argparse
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
data, sample_frequency = sf.read(args.filename, dtype="float32")
try:
    sd.play(
        data,
        sample_frequency,
        device=args.device,
    )
    # wait:
    # 재생 혹은 녹음 중 버퍼 오버런, 언더런이 발생하면 `CallbackFalgs` 객체를 반환합니다.
    # 정상적으로 작업을 마치면 `None`을 반환합니다.
    status = sd.wait()
except KeyboardInterrupt:
    parser.exit("프로그램을 중단시켰습니다")
except Exception as e:
    parser.exit(f"{type(e).__name__}: {str(e)}")

# 재생을 정상적으로 마치지 못하면 실행됩니다.
if status:
    parser.exit(f"재생에 실패하였습니다: {str(status)}")
