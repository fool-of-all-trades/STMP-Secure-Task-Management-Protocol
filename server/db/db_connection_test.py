from db import get_connection

def test_connection():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]

                cur.execute("SELECT current_database();")
                db_name = cur.fetchone()[0]

                print("Połączenie działa")
                print("Baza:", db_name)
                print("PostgreSQL:", version)

    except Exception as e:
        print("Błąd połączenia:")
        print(type(e).__name__, e)

if __name__ == "__main__":
    test_connection()