"""
Migration script to add multi-condition rank system.
Creates rank_conditions table and migrates existing XP-based ranks.
"""
from app import create_app
from models import db, CustomRank, RankCondition

def migrate():
    app = create_app()
    
    with app.app_context():
        print("Starting rank conditions migration...")
        
        # Create rank_conditions table
        print("Creating rank_conditions table...")
        db.create_all()
        print("✓ Table created")
        
        # Migrate existing ranks with min_xp to use conditions
        print("\nMigrating existing ranks...")
        ranks = CustomRank.query.all()
        migrated_count = 0
        
        for rank in ranks:
            # Check if rank has min_xp set and no conditions yet
            if rank.min_xp is not None and rank.min_xp > 0 and not rank.conditions:
                # Create a total_xp condition
                condition = RankCondition(
                    rank_id=rank.id,
                    condition_type='total_xp',
                    threshold=rank.min_xp
                )
                db.session.add(condition)
                migrated_count += 1
                print(f"  ✓ Migrated '{rank.name}' (Level {rank.level}) - {rank.min_xp} XP")
        
        if migrated_count > 0:
            db.session.commit()
            print(f"\n✓ Successfully migrated {migrated_count} rank(s)")
        else:
            print("\n  No ranks to migrate")
        
        print("\n✅ Migration complete!")
        print("\nYou can now:")
        print("  - Add multiple conditions to ranks")
        print("  - Use YouTube analytics, streaks, and other condition types")
        print("  - Existing XP-based ranks will continue to work as before")

if __name__ == '__main__':
    migrate()
