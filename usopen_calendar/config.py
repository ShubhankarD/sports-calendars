from zoneinfo import ZoneInfo

# ---------- Config ----------
ET = ZoneInfo("America/New_York")
BASE_URL = "https://www.usopen.org/en_US/scores/feeds/2025/schedule/scheduleDays.json"
TOURNAMENT_URL = "https://www.usopen.org/en_US/cms/feeds/tournament_schedule.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 20  # seconds
DEFAULT_EVENT_HOURS = 2

# Skip early practice/qualifying days by default
INCLUDE_BEFORE_TOURNDAY = 7  # minimum tournDay to include

CAL_METADATA = {
    "name": "US Open 2025",
    "timezone": "America/New_York",
    "refresh_interval": "PT1H",
    "published_ttl": "PT1H",
    "prodid": "-//Your Org//US Open 2025//EN",
    "method": "PUBLISH",
}
