import psycopg2
import os

DATABASE_URL = os.environ.get('DATABASE_URL')

query = """CREATE TABLE playlist (

spotify_id text,
telegram_id text

);"""
with psycopg2.connect(DATABASE_URL, sslmode='require') as con:
    with con.cursor() as cursor:
        cursor.execute(query)
