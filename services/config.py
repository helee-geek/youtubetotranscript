import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

COOKIES_FILE = Path(os.getenv("YOUTUBE_COOKIES_FILE", BASE_DIR / "cookies.txt"))
HTTP_PROXY = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
HTTPS_PROXY = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")

_cookies_content = os.getenv("YOUTUBE_COOKIES_CONTENT")
if _cookies_content and not COOKIES_FILE.is_file():
    COOKIES_FILE.write_text(_cookies_content, encoding="utf-8")

IP_BLOCK_HELP = (
    "YouTube is temporarily blocking your IP (too many requests).\n\n"
    "To fix and keep testing:\n"
    "1. Wait 30-60 minutes without making requests\n"
    "2. Export browser cookies (see README) into cookies.txt in the project folder\n"
    "3. Restart the server\n"
    "4. Avoid clicking 'Get Transcript' repeatedly while testing\n"
    "5. Optional: set HTTP_PROXY / HTTPS_PROXY in .env for a residential proxy"
)
