from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import os
import json
import pandas as pd
import io
from datetime import date

app = Flask(__name__)
load_dotenv()
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

firebase_config_json = os.getenv('FIREBASE_CONFIG')
if not firebase_config_json:
    raise ValueError("FIREBASE_CONFIG environment variable not set")
try:
    firebase_config = json.loads(firebase_config_json)
except json.JSONDecodeError as e:
    raise ValueError("Invalid FIREBASE_CONFIG JSON format") from e

cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred)
db = firestore.client()

def fetch_firestore_data():
    docs = db.collection('enroll').stream()
    data = []
    for doc in docs:
        doc_data = doc.to_dict()
        doc_data['id'] = doc.id
        data.append(doc_data)
    return data

def update_mock_record(student_ref, mock_data):
    student_doc = student_ref.get()
    if student_doc.exists:
        student_data = student_doc.to_dict()
        mock_records = student_data.get('mock', [])
        today = date.today()
        recent_mock = None
        for m in mock_records:
            if 'Date' in m and (today - datetime.strptime(m['Date'], '%Y-%m-%d').date()).days <= 5:
                if 'hr_assessment' in m and 'technical_assessment' in m and 'group_discussion' in m:
                    recent_mock = m
                    break
        if recent_mock:
            mock_id = recent_mock['id']
            updated_mock_data = {
                'Date': str(date.today()),
                'HR name': session['username'],
                'hr_assessment': mock_data.get('hr_assessment', recent_mock.get('hr_assessment')),
                'technical_assessment': mock_data.get('technical_assessment', recent_mock.get('technical_assessment')),
                'group_discussion': mock_data.get('group_discussion', recent_mock.get('group_discussion'))
            }
            student_ref.update({
                f'mock.{mock_id}': updated_mock_data
            })
        else:
            mock_data['Date'] = str(date.today())
            mock_data['GD mentor'] = session['username']
            mock_count = len(mock_records) + 1
            mock_id = f'mock{mock_count}'
            student_ref.update({
                f'mock.{mock_id}': mock_data
            })
        return mock_id
    return None

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('Index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_ref = db.collection('faculty').document(username)
        user = user_ref.get()
        if user.exists:
            user_data = user.to_dict()
            if user_data.get('passkey') == password:
                session['username'] = username
                session['role'] = user_data.get('role')
                return redirect(url_for('index'))
            else:
                return 'Invalid password'
        else:
            return 'User does not exist'
    return render_template('Login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        designation = request.form.get('Designation')
        name = request.form.get('Name')
        role = request.form.get('Role')
        user_ref = db.collection('faculty').document(username)
        user_ref.set({
            'username': username,
            'designation': designation,
            'name': name,
            'passkey': password,
            'role': role
        })
        return redirect(url_for('login'))
    return render_template('Signup.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/search', methods=['GET'])
def search():
    if 'username' not in session:
        return redirect(url_for('login'))
    query = request.args.get('q')
    department = request.args.get('department')
    data = fetch_firestore_data()
    if query:
        data = [d for d in data if query.lower() in d.get('Name', '').lower()]
    if department and department != "All":
        data = [d for d in data if d.get('Branch') == department]
    return jsonify(data)

@app.route('/update', methods=['POST'])
def update():
    if 'username' not in session:
        return redirect(url_for('login'))
    try:
        doc_id = request.form.get('id')
        hr_assessment = int(request.form.get('hr_assessment'))
        technical_assessment = int(request.form.get('technical_assessment'))
        group_discussion = request.form.get('group_discussion')
        mock_data = {
            'Date': str(date.today()),
            'Name': session['username'],
            'hr_assessment': hr_assessment,
            'technical_assessment': technical_assessment,
            'group_discussion': group_discussion,
        }
        student_ref = db.collection('enroll').document(doc_id)
        mock_id = update_mock_record(student_ref, mock_data)
        if mock_id:
            return jsonify({'success': True, 'mock_id': mock_id})
        else:
            return jsonify({'success': False, 'message': 'Failed to update mock'})
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': str(e)})

@app.route('/hrt', methods=['GET', 'POST'])
def hrt():
    if 'username' not in session:
        return redirect(url_for('login'))
    data = fetch_firestore_data()
    departments = set(d.get('Branch') for d in data)
    return render_template('hrt.html', data=data, departments=departments)

@app.route('/update_hrt', methods=['POST'])
def update_hrt():
    if 'username' not in session:
        return redirect(url_for('login'))
    try:
        doc_id = request.form.get('id')
        hr_assessment = int(request.form.get('hr_assessment'))
        technical_assessment = int(request.form.get('technical_assessment'))
        mock_data = {
            'Date': str(date.today()),
            'Name': session['username'],
            'hr_assessment': hr_assessment,
            'technical_assessment': technical_assessment
        }
        student_ref = db.collection('enroll').document(doc_id)
        mock_id = update_mock_record(student_ref, mock_data)
        if mock_id:
            return jsonify({'success': True, 'mock_id': mock_id})
        else:
            return jsonify({'success': False, 'message': 'Failed to update mock'})
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': str(e)})

@app.route('/gd', methods=['GET', 'POST'])
def gd():
    if 'username' not in session:
        return redirect(url_for('login'))
    data = fetch_firestore_data()
    departments = set(d.get('Branch') for d in data)
    return render_template('gd.html', data=data, departments=departments)

@app.route('/search_gd', methods=['GET'])
def search_gd():
    if 'username' not in session:
        return redirect(url_for('login'))
    query = request.args.get('q', '')
    department = request.args.get('department', 'All')
    data = fetch_firestore_data()
    if query:
        data = [d for d in data if query.lower() in d.get('Name', '').lower()]
    if department and department != "All":
        data = [d for d in data if d.get('Branch') == department]
    return jsonify(data)

@app.route('/update_gd', methods=['POST'])
def update_gd():
    if 'username' not in session:
        return redirect(url_for('login'))
    try:
        doc_id = request.form.get('id')
        group_discussion = request.form.get('group_discussion')
        today = date.today()
        mock_data = {
            'Date': str(today.isoformat()),
            'Name': session['username'],
            'group_discussion': group_discussion
        }
        student_ref = db.collection('enroll').document(doc_id)
        mock_id = update_mock_record(student_ref, mock_data)
        if mock_id:
            return jsonify({'success': True, 'mock_id': mock_id})
        else:
            return jsonify({'success': False, 'message': 'Failed to update mock'})
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin')
def admin():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    data = fetch_firestore_data()
    departments = sorted({d.get('Branch') for d in data if 'Branch' in d})
    return render_template('admin.html', departments=departments)

@app.route('/admin/download')
def download_data():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    department = request.args.get('department', 'All')
    data = fetch_firestore_data()
    if department != 'All':
        data = [d for d in data if d.get('Branch') == department]
    df = pd.DataFrame(data)
    excel_stream = io.BytesIO()
    df.to_excel(excel_stream, index=False)
    excel_stream.seek(0)
    return send_file(excel_stream, download_name='data.xlsx', as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
