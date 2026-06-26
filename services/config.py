import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

HTTP_PROXY = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
HTTPS_PROXY = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")

IP_BLOCK_HELP = (
    "YouTube blocked this request (too many requests or bot check).\n\n"
    "Try again in 30-60 minutes, use a different network (e.g. mobile hotspot), "
    "and avoid clicking 'Get Transcript' repeatedly."
)
