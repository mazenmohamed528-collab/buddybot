import pyodbc

server = r"localhost"   # change if needed
database = "FCI_UNIVERSITY"

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={server};"
    f"DATABASE={database};"
    "Trusted_Connection=yes;"
    "Encrypt=no;"
    "TrustServerCertificate=yes;"
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sys.tables")
rows = cursor.fetchall()

print("Connected successfully!")
print("Tables:")

for row in rows:
    print("-", row[0])

conn.close()

