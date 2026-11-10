import sys
import os

# Обеспечиваем поддержку UTF-8 в выводе консоли Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("Starting AI Moderation Server...")
    print("Public Web UI: http://localhost:8000")
    print("Admin Panel:   http://localhost:8000/admin")
    print("API Swagger:   http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
