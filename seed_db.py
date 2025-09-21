import csv
import sqlite3

# --- 1. SETUP THE DATABASE ---

# This creates or connects to a database file called 'movies.db'
connection = sqlite3.connect('movies.db')
cursor = connection.cursor()

# Create the 'movies' table if it doesn't already exist.
# Using 'IF NOT EXISTS' is good practice.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        title TEXT NOT NULL
    )
""")

# --- 2. READ AND INSERT THE DATA ---

# Open the TSV file for reading
with open('top1000.csv', 'r', newline='', encoding='utf-8') as file:
    reader = csv.reader(file, delimiter=',')
    next(reader)  # Skip the header row

    # Loop through each row in the file
    for row in reader:
        # Get the title from the second column (index 1)
        title = row[1]
        
        # Insert it into the database
        cursor.execute("INSERT INTO movies (title) VALUES (?)", (title,))

# --- 3. SAVE AND CLOSE ---

connection.commit()  # Save the changes to the database
connection.close()   # Close the connection

print("Database 'movies.db' has been created and populated.")