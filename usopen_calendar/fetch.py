from typing import Any
import requests
from requests.adapters import HTTPAdapter, Retry
from .config import HEADERS, TIMEOUT

# Use a session with basic retries
_session = requests.Session()
_session.headers.update(HEADERS)
retries = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)
_session.mount("https://", HTTPAdapter(max_retries=retries))
_session.mount("http://", HTTPAdapter(max_retries=retries))

def fetch_json(url: str) -> Any:
    r = _session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()
