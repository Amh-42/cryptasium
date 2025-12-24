"""
Database seeding script for Cryptasium application.
Run this script once to seed initial configuration data.
Usage: python seed_db.py
"""

import os
import sys

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import (
    db, SystemSettings, Rank, ContentPointValue, 
    DailyTask, WeeklyRequirement, WeeklyPostingSchedule
)
from datetime import time


def check_if_seeded():
    """Check if database has already been seeded"""
    return SystemSettings.query.first() is not None


def seed_system_settings():
    """Seed system settings"""
    if SystemSettings.query.first():
        print("[SKIP] System settings already exist")
        return False
    
    settings = [
        ('points_name', 'XP', 'Name for the point system (XP, PT, Points, etc.)'),
        ('daily_xp_goal', '50', 'Daily XP goal to maintain streak'),
        ('perfect_week_bonus', '500', 'Bonus XP for completing a perfect week'),
        ('shorts_duration_max', '60', 'Maximum duration in seconds for Shorts'),
        ('short_longs_duration_max', '300', 'Maximum duration in seconds for Short Longs (5 min)'),
        ('mid_longs_duration_max', '480', 'Maximum duration in seconds for Mid Longs (8 min)'),
        ('site_name', 'Cryptasium', 'Website name'),
        ('max_rank_code', 'AL', 'Code of the maximum achievable rank'),
    ]
    
    for key, value, desc in settings:
        setting = SystemSettings(key=key, value=value, description=desc)
        db.session.add(setting)
    
    db.session.commit()
    print("[OK] Seeded system settings")
    return True


def seed_ranks():
    """Seed rank configurations with PNG badge icons"""
    if Rank.query.first():
        print("[SKIP] Ranks already exist")
        return False
    
    # Ranks with PNG badge icons (stored in static/badges/PNG/)
    ranks = [
        (0, 'UN', 'Unranked', 0, 0, 0, 0, '#666666', 'PNG/UN.png', False),
        (1, 'BT', 'Beginner Token', 100, 5, 200, 1, '#8B4513', 'PNG/BT.png', False),
        (2, 'HB', 'Habit Builder', 2500, 50, 5000, 10, '#CD853F', 'PNG/HB.png', False),
        (3, 'SO', 'Standing Out', 10000, 1000, 20000, 50, '#B8860B', 'PNG/SO.png', False),
        (4, 'TP', 'Team Player', 50000, 5000, 100000, 100, '#4682B4', 'PNG/TP.png', False),
        (5, 'FL', 'Flight Lead', 200000, 10000, 400000, 200, '#6A5ACD', 'PNG/FL.png', False),
        (6, 'MS', 'Master Strategist', 500000, 25000, 1000000, 350, '#FFD700', 'PNG/MS.png', False),
        (7, 'EA', 'Empire Architect', 1000000, 50000, 2500000, 500, '#9932CC', 'PNG/EA.png', False),
        (8, 'LF', 'Legacy Forger', 5000000, 100000, 10000000, 750, '#00CED1', 'PNG/LF.png', False),
        (9, 'AL', 'Alpha Legend', 20000000, 1000000, 50000000, 1000, '#FF2222', 'PNG/AL.png', True),
    ]
    
    for level, code, name, points, subs, views, content, color, icon, is_max in ranks:
        rank = Rank(
            level=level, code=code, name=name,
            points_required=points, subscribers_required=subs,
            views_required=views, content_required=content,
            color=color, icon=icon, is_max_rank=is_max
        )
        db.session.add(rank)
    
    db.session.commit()
    print("[OK] Seeded ranks with PNG badge icons")
    return True


def seed_content_point_values():
    """Seed content point values with Phosphor icons"""
    if ContentPointValue.query.first():
        print("[SKIP] Content point values already exist")
        return False
    
    content_points = [
        ('blog', 'Blog Post', 50, 'Technical writing and articles', 'ph-article'),
        ('shorts', 'Shorts', 100, 'Short-form video content (< 1 min)', 'ph-lightning'),
        ('short_longs', 'Short Longs', 200, 'Videos under 5 minutes', 'ph-film-strip'),
        ('podcast', 'Podcast', 400, 'Audio/Interview content', 'ph-microphone'),
        ('mid_longs', 'Mid Longs', 800, 'Videos 5-8 minutes', 'ph-video'),
        ('longs', 'Long Form', 1000, 'Videos over 8 minutes', 'ph-youtube-logo'),
        ('subscriber', 'Subscriber', 20, 'Points per subscriber', 'ph-users'),
        ('view', 'View', 0.5, 'Points per view', 'ph-eye'),
    ]
    
    for ctype, name, points, desc, icon in content_points:
        cpv = ContentPointValue(
            content_type=ctype, name=name, points=points,
            description=desc, icon=icon
        )
        db.session.add(cpv)
    
    db.session.commit()
    print("[OK] Seeded content point values with Phosphor icons")
    return True


def seed_daily_tasks():
    """Seed daily task configurations with Phosphor icons"""
    if DailyTask.query.first():
        print("[SKIP] Daily tasks already exist")
        return False
    
    daily_tasks = [
        ('research', 'Research & Scripting', 'Topic Relevance', 15, 'ph-magnifying-glass', 1),
        ('recording', 'Voiceover & Editing', 'Retention', 20, 'ph-video-camera', 2),
        ('engagement', 'Title, Thumbnail & Hook', 'CTR Optimization', 10, 'ph-cursor-click', 3),
        ('learning', 'Learning & Skill Up', 'Level Up', 5, 'ph-trend-up', 4),
    ]
    
    for key, name, desc, xp, icon, order in daily_tasks:
        task = DailyTask(
            task_key=key, name=name, description=desc,
            xp_value=xp, icon=icon, display_order=order
        )
        db.session.add(task)
    
    db.session.commit()
    print("[OK] Seeded daily tasks with Phosphor icons")
    return True


def seed_weekly_requirements():
    """Seed weekly requirement configurations with Phosphor icons"""
    if WeeklyRequirement.query.first():
        print("[SKIP] Weekly requirements already exist")
        return False
    
    weekly_reqs = [
        ('long_form', 'Long Form (YouTube)', 'The "Boss Battle"', 1, 'ph-target', 1),
        ('shorts', 'Shorts (YouTube)', 'The "Skirmishes"', 2, 'ph-sword', 2),
        ('blog', 'Blog (Technical Writing)', 'The "Knowledge Base"', 1, 'ph-note-pencil', 3),
        ('podcast', 'Podcast (Audio/Interview)', 'The "Networking/Philosophy"', 1, 'ph-microphone-stage', 4),
    ]
    
    for ctype, name, desc, count, icon, order in weekly_reqs:
        req = WeeklyRequirement(
            content_type=ctype, name=name, description=desc,
            required_count=count, icon=icon, display_order=order
        )
        db.session.add(req)
    
    db.session.commit()
    print("[OK] Seeded weekly requirements with Phosphor icons")
    return True


def seed_weekly_posting_schedule():
    """Seed default weekly posting schedule with optimized posting days"""
    if WeeklyPostingSchedule.query.first():
        print("[SKIP] Weekly posting schedule already exists")
        return False
    
    # Optimized posting schedule for maximum engagement
    # Based on YouTube & blogging best practices
    schedule = [
        # YouTube Long Form - Saturday (high engagement day)
        {
            'content_type': 'youtube',
            'content_label': 'YouTube Long Form',
            'day_of_week': 5,  # Saturday
            'preferred_time': time(14, 0),  # 2:00 PM
            'color': '#ff0000',
            'icon': 'ph-youtube-logo'
        },
        # Short 1 - Tuesday (mid-week boost)
        {
            'content_type': 'short1',
            'content_label': 'YouTube Short #1',
            'day_of_week': 1,  # Tuesday
            'preferred_time': time(12, 0),  # 12:00 PM
            'color': '#ff4444',
            'icon': 'ph-video'
        },
        # Short 2 - Thursday (pre-weekend engagement)
        {
            'content_type': 'short2',
            'content_label': 'YouTube Short #2',
            'day_of_week': 3,  # Thursday
            'preferred_time': time(18, 0),  # 6:00 PM
            'color': '#ff4444',
            'icon': 'ph-video'
        },
        # Blog - Wednesday (mid-week content)
        {
            'content_type': 'blog',
            'content_label': 'Blog Post',
            'day_of_week': 2,  # Wednesday
            'preferred_time': time(9, 0),  # 9:00 AM
            'color': '#0ea5e9',
            'icon': 'ph-article'
        },
        # Podcast - Monday (start of week)
        {
            'content_type': 'podcast',
            'content_label': 'Podcast Episode',
            'day_of_week': 0,  # Monday
            'preferred_time': time(8, 0),  # 8:00 AM
            'color': '#a855f7',
            'icon': 'ph-microphone'
        },
    ]
    
    for item in schedule:
        entry = WeeklyPostingSchedule(**item)
        db.session.add(entry)
    
    db.session.commit()
    print("[OK] Seeded weekly posting schedule")
    return True


def seed_all():
    """Run all seeders"""
    print("\n=== Starting Database Seed ===\n")
    
    seeded_any = False
    seeded_any |= seed_system_settings()
    seeded_any |= seed_ranks()
    seeded_any |= seed_content_point_values()
    seeded_any |= seed_daily_tasks()
    seeded_any |= seed_weekly_requirements()
    seeded_any |= seed_weekly_posting_schedule()
    
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
    DailyTask.query.delete()
    WeeklyRequirement.query.delete()
    ContentPointValue.query.delete()
    Rank.query.delete()
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

