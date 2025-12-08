from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
from indic_transliteration import sanscript

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

def get_unique_house_names_both():
    # Get unique house names from both databases
    conn1 = sqlite3.connect('voters_1.db')
    cursor1 = conn1.cursor()
    cursor1.execute("SELECT DISTINCT house_name FROM voters ORDER BY house_name")
    names1 = [row[0] for row in cursor1.fetchall()]
    conn1.close()

    conn2 = sqlite3.connect('voters.db')
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT DISTINCT house_name FROM voters ORDER BY house_name")
    names2 = [row[0] for row in cursor2.fetchall()]
    conn2.close()

    # Combine and remove duplicates
    all_names = list(set(names1 + names2))
    all_names.sort()
    return all_names

def get_unique_house_nos_both():
    # Get unique house nos from both databases
    conn1 = sqlite3.connect('voters_1.db')
    cursor1 = conn1.cursor()
    cursor1.execute("SELECT DISTINCT house_no FROM voters ORDER BY house_no")
    nos1 = [row[0] for row in cursor1.fetchall()]
    conn1.close()

    conn2 = sqlite3.connect('voters.db')
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT DISTINCT house_no FROM voters ORDER BY house_no")
    nos2 = [row[0] for row in cursor2.fetchall()]
    conn2.close()

    # Combine and remove duplicates
    all_nos = list(set(nos1 + nos2))
    all_nos.sort()
    return all_nos

def get_unique_names_both():
    # Get unique names from both databases
    conn1 = sqlite3.connect('voters_1.db')
    cursor1 = conn1.cursor()
    cursor1.execute("SELECT DISTINCT name FROM voters ORDER BY name")
    names1 = [row[0] for row in cursor1.fetchall()]
    conn1.close()

    conn2 = sqlite3.connect('voters.db')
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT DISTINCT name FROM voters ORDER BY name")
    names2 = [row[0] for row in cursor2.fetchall()]
    conn2.close()

    # Combine and remove duplicates
    all_names = list(set(names1 + names2))
    all_names.sort()
    return all_names

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

def get_voters_by_name_phonetic(malayalam_name, booth_no):
    db_name = get_db_name(booth_no)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voters WHERE name LIKE ?", (f'%{malayalam_name}%',))
    voters = cursor.fetchall()
    conn.close()
    return voters

@app.route('/')
def index():
    house_names = get_unique_house_names_both()
    house_nos = get_unique_house_nos_both()
    names = get_unique_names_both()
    return render_template('index.html', house_names=house_names, house_nos=house_nos, names=names)

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
        # Transliterate English to Malayalam for phonetic search
        malayalam_name = sanscript.transliterate(name, sanscript.ITRANS, sanscript.MALAYALAM)
        voters = get_voters_by_name_phonetic(malayalam_name, booth_no)
        return render_template('details.html', name=name, voters=voters, booth_no=booth_no)
    else:
        return "No valid filter selected", 400

@app.route('/comparison')
def comparison():
    house_names = get_unique_house_names_both()
    house_nos = get_unique_house_nos_both()
    return render_template('comparison.html', house_names=house_names, house_nos=house_nos)

@app.route('/compare_results', methods=['POST'])
def compare_results():
    comparison_type = request.form.get('comparison_type')
    value = request.form.get('value')

    if not comparison_type or not value:
        return "Invalid comparison parameters", 400

    # Fetch from both DBs
    if comparison_type == 'house_name':
        conn1 = sqlite3.connect('voters_1.db')
        cursor1 = conn1.cursor()
        cursor1.execute("SELECT * FROM voters WHERE house_name = ?", (value,))
        voters1 = cursor1.fetchall()
        conn1.close()

        conn2 = sqlite3.connect('voters.db')
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT * FROM voters WHERE house_name = ?", (value,))
        voters2 = cursor2.fetchall()
        conn2.close()
    elif comparison_type == 'house_no':
        conn1 = sqlite3.connect('voters_1.db')
        cursor1 = conn1.cursor()
        cursor1.execute("SELECT * FROM voters WHERE house_no = ?", (value,))
        voters1 = cursor1.fetchall()
        conn1.close()

        conn2 = sqlite3.connect('voters.db')
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT * FROM voters WHERE house_no = ?", (value,))
        voters2 = cursor2.fetchall()
        conn2.close()
    else:
        return "Invalid comparison type", 400

    # Convert to sets of tuples for comparison
    set1 = set(tuple(v) for v in voters1)
    set2 = set(tuple(v) for v in voters2)

    common = set1 & set2
    unique1 = set1 - set2
    unique2 = set2 - set1

    return render_template('compare_results.html', comparison_type=comparison_type, value=value,
                           voters1=voters1, voters2=voters2, common=list(common), unique1=list(unique1), unique2=list(unique2))

@app.route('/api/search_suggestions')
def search_suggestions():
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'name')  # default to name, but can be house_name or house_no
    if not query:
        return jsonify([])

    # Transliterate English to Malayalam using roman scheme for better phonetic accuracy
    malayalam_query = sanscript.transliterate(query, sanscript.roman, sanscript.MALAYALAM)

    # Search in both databases
    suggestions = set()

    column = 'name' if search_type == 'name' else ('house_name' if search_type == 'house_name' else 'house_no')

    for db_name in ['voters_1.db', 'voters.db']:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute(f"SELECT DISTINCT {column} FROM voters WHERE {column} LIKE ?", (f'%{malayalam_query}%',))
        values = [row[0] for row in cursor.fetchall()]
        suggestions.update(values)
        conn.close()

    return jsonify(list(suggestions))

if __name__ == '__main__':
    app.run(debug=True)
