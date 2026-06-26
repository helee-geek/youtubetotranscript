import os


def is_cloud_host() -> bool:
    """True on cloud platforms whose IPs YouTube often blocks (Render, Railway, etc.)."""
    return bool(
        os.getenv("RENDER")
        or os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("FLY_APP_NAME")
        or os.getenv("VERCEL")
        or os.getenv("DYNO")
    )


DEMO_TUNNEL_HINT = (
    "YouTube blocked this server (cloud IPs are treated as bots). "
    "Free fix: on your laptop run ./scripts/run-demo-tunnel.sh, "
    "share the trycloudflare.com URL it prints, and keep that terminal open during your demo."
)
