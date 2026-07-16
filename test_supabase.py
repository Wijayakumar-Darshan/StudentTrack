import os
from dotenv import load_dotenv
from pathlib import Path

# Force load .env from the same directory as this script
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

url = os.getenv("DATABASE_URL")
if not url:
    print("❌ DATABASE_URL not found in .env file.")
    print(f"Looking for .env at: {env_path}")
    exit(1)

url = url.strip().strip('"')
print("URL:", url)

import psycopg2

try:
    conn = psycopg2.connect(url)
    print("✅ Connected to Supabase!")
    conn.close()
except Exception as e:
    print("❌ Error:", e)