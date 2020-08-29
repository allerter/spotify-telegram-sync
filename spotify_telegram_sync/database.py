import psycopg2
from constants import DATABASE_URL


def get_key_value(data):
    key = list(data.keys())[0]
    value = data[key]
    return key, value


def database(action, data=None):
    """all the database requests go through here"""
    res = None
    if action == 'insert':
        values = ','.join([f"""('{x[0]}', '{x[1]}')""" for x in data])
        query = f"""INSERT INTO playlist VALUES {values};"""

    elif action == 'select':
        query = """SELECT * FROM playlist"""
        if data:
            key, key_value = get_key_value(data)
            values = f"""'{"','".join(key_value)}'"""
            query += f' where {key} in ({values})'

    elif action == 'delete':
        key, key_value = get_key_value(data)
        values = f"""'{"','".join(key_value)}'"""
        query = f"""DELETE FROM playlist WHERE {key} in ({values});"""
    # connect to database
    with psycopg2.connect(DATABASE_URL, sslmode='require') as con:
        with con.cursor() as cursor:
            cursor.execute(query)
            if action == 'select':
                res = cursor.fetchall()
    return res