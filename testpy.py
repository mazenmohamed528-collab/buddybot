import pyodbc

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "Trusted_Connection=yes;"
    "DATABASE=master;"
    "Encrypt=no;"
    "TrustServerCertificate=yes;"
)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sys.databases ORDER BY name")
for row in cursor.fetchall():
    print(row[0])

conn.close()
