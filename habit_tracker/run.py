#!/usr/bin/env python3
"""
HabitFlow - Multi-User Habit Tracker
=====================================
Run this file to start the app:
    python run.py

Then open your browser at:
    http://localhost:5000

Requirements:
    pip install flask
"""
import subprocess, sys, os

def main():
    # Install Flask if needed
    try:
        import flask
    except ImportError:
        print("Installing Flask...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'flask'])

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Init DB and run
    from app import app, init_db
    init_db()
    print("\n" + "="*50)
    print("  🌱 HabitFlow is running!")
    print("  Open: http://localhost:5000")
    print("  Press Ctrl+C to stop")
    print("="*50 + "\n")
    app.run(debug=False, port=5000, host='0.0.0.0')

if __name__ == '__main__':
    main()
