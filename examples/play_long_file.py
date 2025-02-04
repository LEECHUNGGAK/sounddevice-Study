import argparse
import queue
import sys
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
# 여기까지 play_file.py와 동일합니다.

parser.add_argument(
    "-b",
    "--blocksize",
    type=int,
    default=2048,
    help="블록의 크기 (내정값: %(default)s)",
)

parser.add_argument(
    "-q",
    "--buffersize",
    type=int,
    default=20,
    help="버퍼링에 사용할 블록의 개수 (내정값: %(default)s)",
)

args = parser.parse_args(remaining)
if args.blocksize == 0:
    parser.error("블록의 크기를 0으로 설정할 수 없습니다")
if args.buffersize < 1:
    parser.error("블록의 개수는 1을 초과해야 합니다")

q = queue.Queue(maxsize=args.buffersize)
event = threading.Event()


def callback(outdata, frames, time, status):
    assert frames == args.blocksize
    # frames는 콜백 함수를 호출할 때마다 처리하는 프레임의 길이입니다.
    # 이 값은 블록의 크기와 같아야 합니다.

    if status.output_underflow:
        print(
            "출력 언더런: 블록의 크기를 늘리세요",
            file=sys.stderr,
        )
        # 언더런은 버퍼에 데이터를 추가하는 속도보다 빠르게 데이터를 회수하여 재생할 때 발생합니다.
        # 따라서 언더런이 발생할 때에는 블록의 크기를 늘려,
        # 버퍼에 데이터를 추가하는 속도를 높이고 데이터를 재생하는 시간을 늘립니다.
        raise sd.CallbackAbort

    assert not status

    try:
        data = q.get_nowait()
    except queue.Empty as e:
        print(
            "버퍼가 비어있습니다: 버퍼의 크기를 늘리세요",
            file=sys.stderr,
        )
        raise sd.CallbackAbort from e

    if len(data) < len(outdata):
        outdata[: len(data)] = data
        outdata[len(data) :].fill(0)
        raise sd.CallbackStop

    else:
        outdata[:] = data


try:
    with sf.SoundFile(args.filename) as f:
        for _ in range(args.buffersize):
            data = f.read(args.blocksize)
            if not len(data):
                break
            q.put_nowait(data)
        # 오디오 파일을 블록의 크기만큼 읽어 대기 행렬에 추가합니다
        # 대기 행렬의 크기는 버퍼의 크기와 같습니다.
        # 최종적으로 초기 버퍼를 생성합니다.

        stream = sd.OutputStream(
            device=args.device,
            blocksize=args.blocksize,
            samplerate=f.samplerate,
            channels=f.channels,
            callback=callback,
            finished_callback=event.set,
        )

        with stream:
            timeout = args.blocksize * args.buffersize / f.samplerate
            # 대기 행렬에 추가한 소리의 크기는 블록의 크기 * 버퍼의 크기와 같습니다.
            # 대기 행렬의 전체 항목을 재생하는 시간은 (소리의 크기 / 샘플링 속도)초와 같습니다.

            while len(data):
                data = f.read(args.blocksize)
                q.put(data, timeout=timeout)
                # 대기 행렬의 재생 시간만큼 타임아웃을 지정합니다.
            # 초기 버퍼를 채우고 남은 오디오 파일 데이터를 읽어 버퍼에 추가합니다.
            # 모든 오디오 파일을 읽을 때까지 반복합니다.

            event.wait()
            # 재생이 끝날 때까지 대기합니다.

except KeyboardInterrupt:
    parser.exit("프로그램을 중단시켰습니다")

except queue.Full:
    parser.exit(1)

except Exception as e:
    parser.exit(f"{type(e).__name__}: {str(e)}")
