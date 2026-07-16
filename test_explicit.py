import psycopg2

try:
    conn = psycopg2.connect(
        host="aws-0-ap-southeast-1.pooler.supabase.com",
        port=6543,
        user="postgres.yrulsekmonaduqytjwvu",
        password="CristKingCollege789",
        dbname="postgres",
        sslmode="require"
    )
    print("✅ Connected!")
    conn.close()
except Exception as e:
    print("❌", e)