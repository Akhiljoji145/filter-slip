from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default-secret-key-change-in-production')

def get_db_name(booth_no):
    return 'voters_1.db' if booth_no == '1' else 'voters.db'

def get_unique_house_names(booth_no):
    db_name = get_db_name(booth_no)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT house_name FROM voters ORDER BY house_name")
    names = [row[0] for row in cursor.fetchall()]
    conn.close()
    return names

def get_unique_house_nos(booth_no):
    db_name = get_db_name(booth_no)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT house_no FROM voters ORDER BY house_no")
    nos = [row[0] for row in cursor.fetchall()]
    conn.close()
    return nos

def get_unique_names(booth_no):
    db_name = get_db_name(booth_no)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT name FROM voters ORDER BY name")
    names = [row[0] for row in cursor.fetchall()]
    conn.close()
    return names

def get_voters_by_house_name(house_name, booth_no):
    db_name = get_db_name(booth_no)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voters WHERE house_name = ?", (house_name,))
    voters = cursor.fetchall()
    conn.close()
    # Group by house_no
    groups = {}
    for voter in voters:
        house_no = voter[3]  # house_no is index 3
        if house_no not in groups:
            groups[house_no] = []
        groups[house_no].append(voter)
    return groups

def get_voters_by_house_no(house_no, booth_no):
    db_name = get_db_name(booth_no)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voters WHERE house_no = ?", (house_no,))
    voters = cursor.fetchall()
    conn.close()
    return voters

def get_voters_by_name(name, booth_no):
    db_name = get_db_name(booth_no)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voters WHERE name = ?", (name,))
    voters = cursor.fetchall()
    conn.close()
    return voters

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/select_booth', methods=['POST'])
def select_booth():
    booth_no = request.form['booth_no']
    session['booth_no'] = booth_no
    house_names = get_unique_house_names(booth_no)
    house_nos = get_unique_house_nos(booth_no)
    names = get_unique_names(booth_no)
    return render_template('index.html', booth_no=booth_no, house_names=house_names, house_nos=house_nos, names=names)

@app.route('/get_details', methods=['POST'])
def get_details():
    booth_no = request.form.get('booth_no')
    house_name = request.form.get('house_name')
    house_no = request.form.get('house_no')
    name = request.form.get('name')
    
    if house_name:
        groups = get_voters_by_house_name(house_name, booth_no)
        return render_template('details.html', house_name=house_name, groups=groups, booth_no=booth_no)
    elif house_no:
        voters = get_voters_by_house_no(house_no, booth_no)
        return render_template('details.html', house_no=house_no, voters=voters, booth_no=booth_no)
    elif name:
        voters = get_voters_by_name(name, booth_no)
        return render_template('details.html', name=name, voters=voters, booth_no=booth_no)
    else:
        return "No valid filter selected", 400

if __name__ == '__main__':
    app.run(debug=True)
