from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import json
import hashlib
import os
from datetime import datetime, date, timedelta
import calendar

app = Flask(__name__)
app.secret_key = 'habit_tracker_secret_key_2024'

DB_PATH = 'habit_tracker.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            theme TEXT DEFAULT 'pastel',
            avatar_color TEXT DEFAULT '#f9a8d4'
        );

        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            goal INTEGER DEFAULT 30,
            type TEXT DEFAULT 'daily',
            color TEXT DEFAULT '#f9a8d4',
            icon TEXT DEFAULT '✓',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            archived INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS habit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            completed INTEGER DEFAULT 1,
            UNIQUE(habit_id, log_date),
            FOREIGN KEY(habit_id) REFERENCES habits(id)
        );
    ''')
    conn.commit()
    conn.close()

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

# ─── Pages ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# ─── Auth API ──────────────────────────────────────────────────────────────────

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username','').strip()
    password = data.get('password','')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    conn = get_db()
    try:
        conn.execute('INSERT INTO users (username, password) VALUES (?,?)',
                     (username, hash_password(password)))
        conn.commit()
        user = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        session['user_id'] = user['id']
        session['username'] = user['username']
        return jsonify({'ok': True, 'username': username})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username already taken'}), 409
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username','').strip()
    password = data.get('password','')
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username=? AND password=?',
                        (username, hash_password(password))).fetchone()
    conn.close()
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    session['user_id'] = user['id']
    session['username'] = user['username']
    return jsonify({'ok': True, 'username': username})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/me')
@login_required
def me():
    conn = get_db()
    user = conn.execute('SELECT id, username, theme, avatar_color, created_at FROM users WHERE id=?',
                        (session['user_id'],)).fetchone()
    conn.close()
    return jsonify(dict(user))

# ─── Habits API ────────────────────────────────────────────────────────────────

@app.route('/api/habits', methods=['GET'])
@login_required
def get_habits():
    conn = get_db()
    habits = conn.execute(
        'SELECT * FROM habits WHERE user_id=? AND archived=0 ORDER BY id',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return jsonify([dict(h) for h in habits])

@app.route('/api/habits', methods=['POST'])
@login_required
def add_habit():
    data = request.json
    name = data.get('name','').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    conn = get_db()
    conn.execute(
        'INSERT INTO habits (user_id, name, goal, type, color, icon) VALUES (?,?,?,?,?,?)',
        (session['user_id'], name, data.get('goal', 30),
         data.get('type','daily'), data.get('color','#f9a8d4'), data.get('icon','✓'))
    )
    conn.commit()
    habit = conn.execute('SELECT * FROM habits WHERE user_id=? ORDER BY id DESC LIMIT 1',
                         (session['user_id'],)).fetchone()
    conn.close()
    return jsonify(dict(habit))

@app.route('/api/habits/<int:habit_id>', methods=['PUT'])
@login_required
def update_habit(habit_id):
    data = request.json
    conn = get_db()
    conn.execute(
        'UPDATE habits SET name=?, goal=?, color=?, icon=? WHERE id=? AND user_id=?',
        (data['name'], data['goal'], data['color'], data['icon'],
         habit_id, session['user_id'])
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/habits/<int:habit_id>', methods=['DELETE'])
@login_required
def delete_habit(habit_id):
    conn = get_db()
    conn.execute('UPDATE habits SET archived=1 WHERE id=? AND user_id=?',
                 (habit_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ─── Logs API ──────────────────────────────────────────────────────────────────

@app.route('/api/logs/<int:year>/<int:month>', methods=['GET'])
@login_required
def get_logs(year, month):
    conn = get_db()
    logs = conn.execute(
        '''SELECT hl.habit_id, hl.log_date FROM habit_logs hl
           WHERE hl.user_id=? AND strftime('%Y', log_date)=? AND strftime('%m', log_date)=?''',
        (session['user_id'], str(year), f'{month:02d}')
    ).fetchall()
    conn.close()
    result = {}
    for log in logs:
        hid = log['habit_id']
        result.setdefault(hid, [])
        result[hid].append(log['log_date'])
    return jsonify(result)

@app.route('/api/logs/toggle', methods=['POST'])
@login_required
def toggle_log():
    data = request.json
    habit_id = data['habit_id']
    log_date = data['date']
    conn = get_db()
    existing = conn.execute(
        'SELECT id FROM habit_logs WHERE habit_id=? AND log_date=? AND user_id=?',
        (habit_id, log_date, session['user_id'])
    ).fetchone()
    if existing:
        conn.execute('DELETE FROM habit_logs WHERE id=?', (existing['id'],))
        status = 'removed'
    else:
        conn.execute(
            'INSERT INTO habit_logs (habit_id, user_id, log_date) VALUES (?,?,?)',
            (habit_id, session['user_id'], log_date)
        )
        status = 'added'
    conn.commit()
    conn.close()
    return jsonify({'status': status})

# ─── Stats API ─────────────────────────────────────────────────────────────────

@app.route('/api/stats/<int:year>/<int:month>')
@login_required
def get_stats(year, month):
    uid = session['user_id']
    conn = get_db()
    
    days_in_month = calendar.monthrange(year, month)[1]
    
    habits = conn.execute(
        'SELECT * FROM habits WHERE user_id=? AND archived=0', (uid,)
    ).fetchall()
    
    logs = conn.execute(
        '''SELECT habit_id, log_date FROM habit_logs
           WHERE user_id=? AND strftime('%Y',log_date)=? AND strftime('%m',log_date)=?''',
        (uid, str(year), f'{month:02d}')
    ).fetchall()
    
    log_set = {}
    for l in logs:
        log_set.setdefault(l['habit_id'], set()).add(l['log_date'])
    
    today = date.today()
    stats = []
    for h in habits:
        completed_days = log_set.get(h['id'], set())
        count = len(completed_days)
        goal = h['goal']
        pct = round(count / goal * 100) if goal > 0 else 0

        # Streak calculation
        streak = 0
        d = today
        while True:
            ds = d.strftime('%Y-%m-%d')
            if ds in completed_days:
                streak += 1
                d -= timedelta(days=1)
            else:
                break
        
        # Longest streak
        sorted_dates = sorted(completed_days)
        longest = 0
        cur = 0
        prev = None
        for ds in sorted_dates:
            dt = datetime.strptime(ds, '%Y-%m-%d').date()
            if prev and (dt - prev).days == 1:
                cur += 1
            else:
                cur = 1
            longest = max(longest, cur)
            prev = dt

        stats.append({
            'habit_id': h['id'],
            'name': h['name'],
            'color': h['color'],
            'icon': h['icon'],
            'goal': goal,
            'completed': count,
            'pct': pct,
            'streak': streak,
            'longest_streak': longest,
        })
    
    # Daily totals for chart
    daily_totals = {}
    for day in range(1, days_in_month + 1):
        ds = f'{year}-{month:02d}-{day:02d}'
        total_habits = len(habits)
        done = sum(1 for h in habits if ds in log_set.get(h['id'], set()))
        daily_totals[day] = {'done': done, 'total': total_habits,
                             'pct': round(done/total_habits*100) if total_habits else 0}
    
    # Overall
    all_possible = len(habits) * days_in_month
    all_done = sum(len(v) for v in log_set.values())
    overall_pct = round(all_done / all_possible * 100) if all_possible else 0
    
    conn.close()
    return jsonify({
        'habits': stats,
        'daily': daily_totals,
        'overall_pct': overall_pct,
        'total_completed': all_done,
        'total_possible': all_possible,
        'days_in_month': days_in_month,
    })

@app.route('/api/theme', methods=['POST'])
@login_required
def update_theme():
    data = request.json
    conn = get_db()
    conn.execute('UPDATE users SET theme=?, avatar_color=? WHERE id=?',
                 (data.get('theme','pastel'), data.get('avatar_color','#f9a8d4'),
                  session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
