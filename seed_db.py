"""
Database seeding script for Cryptasium application.
Now uses the dynamic gamification system - seeds are created per-user at signup.
Usage: python seed_db.py
"""

import os
import sys

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, SystemSettings, User, init_user_gamification


def check_if_seeded():
    """Check if database has already been seeded"""
    return SystemSettings.query.first() is not None


def seed_system_settings():
    """Seed system settings"""
    if SystemSettings.query.first():
        print("[SKIP] System settings already exist")
        return False
    
    settings = [
        ('site_name', 'Cryptasium', 'Website name'),
        ('site_description', 'A gamified content tracking platform', 'Site description'),
    ]
    
    for key, value, desc in settings:
        setting = SystemSettings(key=key, value=value, description=desc)
        db.session.add(setting)
    
    db.session.commit()
    print("[OK] Seeded system settings")
    return True


def seed_demo_user():
    """Seed a demo user with gamification data"""
    if User.query.filter_by(username='demo').first():
        print("[SKIP] Demo user already exists")
        return False
    
    # Create demo user
    user = User(
        username='demo',
        email='demo@example.com'
    )
    user.set_password('demo123')
    db.session.add(user)
    db.session.commit()
    
    # Initialize gamification for demo user
    init_user_gamification(user.id)
    
    print("[OK] Created demo user with gamification setup")
    print("     Username: demo")
    print("     Password: demo123")
    return True


def seed_all():
    """Run all seeders"""
    print("\n=== Starting Database Seed ===\n")
    
    seeded_any = False
    seeded_any |= seed_system_settings()
    seeded_any |= seed_demo_user()
    
    if seeded_any:
        print("\n=== Database Seed Complete ===\n")
    else:
        print("\n=== Database Already Seeded (No Changes) ===\n")
    
    return seeded_any


def reset_and_seed():
    """Reset and reseed all configuration data (dangerous!)"""
    print("\n=== RESETTING AND RESEEDING DATABASE ===\n")
    print("[WARN] This will delete all configuration data!")
    
    confirm = input("Type 'yes' to confirm: ")
    if confirm.lower() != 'yes':
        print("[ABORT] Reset cancelled")
        return False
    
    # Delete existing config data
    SystemSettings.query.delete()
    db.session.commit()
    print("[OK] Cleared existing configuration data")
    
    # Reseed
    seed_all()
    return True


if __name__ == '__main__':
    app = create_app()
    
    with app.app_context():
        # Check for --reset flag
        if len(sys.argv) > 1 and sys.argv[1] == '--reset':
            reset_and_seed()
        else:
            if check_if_seeded():
                print("\n[INFO] Database appears to be already seeded.")
                print("[INFO] Run with --reset flag to reset and reseed.")
                print("[INFO] Checking for missing tables...\n")
            seed_all()
