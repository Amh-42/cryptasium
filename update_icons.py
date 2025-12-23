"""
Script to update emoji icons to Phosphor icon classes in existing database.
Run this once to migrate from emojis to Phosphor icons.
"""

import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Rank, ContentPointValue, DailyTask, WeeklyRequirement


def update_icons():
    """Update all emoji icons to Phosphor icon classes"""
    
    print("\n=== Updating Icons to Phosphor Classes ===\n")
    
    # Update Ranks to use PNG badge icons
    ranks = Rank.query.all()
    for rank in ranks:
        # Set icon to the PNG path based on rank code
        expected_icon = f"PNG/{rank.code}.png"
        if rank.icon != expected_icon:
            old_icon = rank.icon
            rank.icon = expected_icon
            print(f"[OK] Rank {rank.code}: {old_icon} -> {rank.icon}")
        else:
            print(f"[--] Rank {rank.code}: already uses {rank.icon}")
    
    # Update Content Point Values
    content_icon_map = {
        '📝': 'ph-article',
        '⚡': 'ph-lightning',
        '🎬': 'ph-film-strip',
        '🎙️': 'ph-microphone',
        '📹': 'ph-video',
        '🎯': 'ph-youtube-logo',
        '👥': 'ph-users',
        '👁️': 'ph-eye',
    }
    
    content_values = ContentPointValue.query.all()
    for cv in content_values:
        if cv.icon in content_icon_map:
            old_icon = cv.icon
            cv.icon = content_icon_map[cv.icon]
            print(f"[OK] Content {cv.content_type}: {old_icon} -> {cv.icon}")
        elif cv.icon and not cv.icon.startswith('ph-'):
            print(f"[WARN] Unknown content icon: {cv.icon} for {cv.content_type}")
    
    # Update Daily Tasks
    task_icon_map = {
        '📚': 'ph-magnifying-glass',
        '🎬': 'ph-video-camera',
        '💬': 'ph-cursor-click',
        '🎓': 'ph-trend-up',
    }
    
    tasks = DailyTask.query.all()
    for task in tasks:
        if task.icon in task_icon_map:
            old_icon = task.icon
            task.icon = task_icon_map[task.icon]
            print(f"[OK] Task {task.task_key}: {old_icon} -> {task.icon}")
        elif task.icon and not task.icon.startswith('ph-'):
            print(f"[WARN] Unknown task icon: {task.icon} for {task.task_key}")
    
    # Update Weekly Requirements
    weekly_icon_map = {
        '🎯': 'ph-target',
        '⚔️': 'ph-sword',
        '📝': 'ph-note-pencil',
        '🎙️': 'ph-microphone-stage',
    }
    
    weekly_reqs = WeeklyRequirement.query.all()
    for req in weekly_reqs:
        if req.icon in weekly_icon_map:
            old_icon = req.icon
            req.icon = weekly_icon_map[req.icon]
            print(f"[OK] Weekly {req.content_type}: {old_icon} -> {req.icon}")
        elif req.icon and not req.icon.startswith('ph-'):
            print(f"[WARN] Unknown weekly icon: {req.icon} for {req.content_type}")
    
    db.session.commit()
    print("\n=== Icon Update Complete! ===\n")


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        update_icons()

