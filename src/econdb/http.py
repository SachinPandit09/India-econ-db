"""HTTP GET for government sites: browser User-Agent, retries with backoff, per-host spacing."""

import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
MIN_GAP = 0.6  # seconds from the end of one request to the start of the next, per host
RETRY_STATUS = {429, 500, 502, 503, 504}
BACKOFF = (2, 4, 8, 16)  # waits between 5 attempts

CONTEXT = ssl.create_default_context()  # certificate verification stays on
CONTEXT.options |= ssl.OP_LEGACY_SERVER_CONNECT  # api.mospi.gov.in needs legacy renegotiation

_last_done: dict[str, float] = {}


class HTTPFailure(Exception):
    """The request still failed after all retries (or failed with a non-retryable status)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def get(
    url,
    params=None,
    timeout=90,
    opener=urllib.request.urlopen,
    sleep=time.sleep,
    clock=time.monotonic,
):
    """Return the response body. Retries timeouts, 429 and 5xx; never less than MIN_GAP apart."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    host = urllib.parse.urlsplit(url).netloc
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    for wait in (*BACKOFF, None):
        gap = MIN_GAP - (clock() - _last_done.get(host, float("-inf")))
        if gap > 0:
            sleep(gap)
        status = None
        try:
            with opener(request, timeout=timeout, context=CONTEXT) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            status = e.code
            if status not in RETRY_STATUS:
                raise HTTPFailure(f"HTTP {status} for {url}", status) from e
            error = f"HTTP {status}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            error = f"{type(e).__name__}: {e}"
        finally:
            _last_done[host] = clock()
        if wait is None:
            raise HTTPFailure(f"{error} for {url} after {len(BACKOFF) + 1} attempts", status)
        sleep(wait)
