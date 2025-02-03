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
    help="블록의 크기 (내정값: {default})",
)

parser.add_argument(
    "-q",
    "--buffersize",
    type=int,
    default=20,
    help="버퍼링에 사용할 블록의 개수 (내정값: {default})",
)

args = parser.parse_args(remaining)
if args.blocksize == 0:
    parser.error("블록의 크기를 0으로 설정할 수 없습니다")
if args.buffer_size < 1:
    parser.error("블록의 개수는 1을 초과해야 합니다")

q = queue.Queue(maxsize=args.buffersize)
event = threading.Event()


def callback(outdata, frames, time, status):
    assert frames == args.blocksize
    # 샘플링 속도와 블록의 크기는 같아야 합니다.

    if status.output_underflow:
        print(
            "출력 언더런: 블록의 크기를 늘리세요",
            file=sys.stderr,
        )
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


data, sample_frequency = sf.read(args.filename, dtype="float32")
try:
    with sf.SoundFile(args.filename) as f:
        for _ in range(args.buffersize):
            data = f.read(args.blocksize)
            if not data:
                break
            q.put_nowait(data)

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
            while len(data):
                data = f.read(args.blocksize)
                q.put(data, timeout=timeout)
            event.wait()
            # 재생이 끝날 때까지 대기합니다.

except KeyboardInterrupt:
    parser.exit("프로그램을 중단시켰습니다")

except queue.Full:
    parser.exit(1)

except Exception as e:
    parser.exit(f"{type(e).__name__}: {str(e)}")
