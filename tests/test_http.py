import gzip
import urllib.error

import pytest

from econdb import archive, http


class Clock:
    def __init__(self):
        self.now, self.sleeps = 0.0, []

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


def opener_for(outcomes):
    def opener(request, timeout, context):
        outcome = outcomes.pop(0)
        if isinstance(outcome, int):
            raise urllib.error.HTTPError(request.full_url, outcome, "err", {}, None)
        return Response(outcome)

    return opener


def test_retries_5xx_with_backoff_then_succeeds():
    http._last_done.clear()
    clock = Clock()
    body = http.get(
        "https://h/x", opener=opener_for([500, 503, b"ok"]), sleep=clock.sleep, clock=clock
    )
    assert body == b"ok"
    assert [s for s in clock.sleeps if s >= 2] == [2, 4]


def test_gives_up_after_five_attempts_and_never_retries_4xx():
    http._last_done.clear()
    clock = Clock()
    with pytest.raises(http.HTTPFailure):
        http.get("https://h/x", opener=opener_for([500] * 5), sleep=clock.sleep, clock=clock)
    with pytest.raises(http.HTTPFailure) as e:
        http.get("https://h/x", opener=opener_for([400]), sleep=clock.sleep, clock=clock)
    assert e.value.status == 400


def test_requests_to_one_host_are_spaced():
    http._last_done.clear()
    clock = Clock()
    for _ in range(3):
        http.get("https://h/x", opener=opener_for([b"ok"]), sleep=clock.sleep, clock=clock)
    assert clock.sleeps == [http.MIN_GAP, http.MIN_GAP]


def test_archive_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("ECONDB_RAW_DIR", str(tmp_path))
    ref = archive.save("mospi/X/2026-09-11/r1_k_p00001.json.gz", b'{"data":[]}')
    assert archive.load(ref) == b'{"data":[]}'
    assert gzip.decompress((tmp_path / ref).read_bytes()) == b'{"data":[]}'
    assert archive.files("mospi/X") == [ref]
