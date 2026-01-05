from app import app, db
from models import RankCondition, CustomRank

def fix_buckets():
    with app.app_context():
        print("Checking for misconfigured buckets...")
        
        # Strategy:
        # If a RankCondition is 'total_xp' AND has a custom name (not 'Total XP'), it implies a specific bucket goal.
        # Also, check if a Rank has multiple 'total_xp' conditions.
        
        conditions = RankCondition.query.filter_by(condition_type='total_xp').all()
        fixed_count = 0
        
        for c in conditions:
            should_be_bucket = False
            
            # 1. Check name
            if c.custom_name and c.custom_name.strip() not in ['Total XP', 'total_xp', 'XP']:
                should_be_bucket = True
                print(f"Condition {c.id} ('{c.custom_name}') should be bucket due to name.")
            
            # 2. Check siblings
            if not should_be_bucket:
                siblings = RankCondition.query.filter_by(rank_id=c.rank_id, condition_type='total_xp').all()
                if len(siblings) > 1:
                    should_be_bucket = True
                    print(f"Condition {c.id} should be bucket due to multiple XP conditions in Rank {c.rank_id}.")
            
            if should_be_bucket and not c.is_bucket:
                c.is_bucket = True
                fixed_count += 1
                print(f" -> FIXED Condition {c.id}")
        
        if fixed_count > 0:
            db.session.commit()
            print(f"Successfully fixed {fixed_count} conditions.")
        else:
            print("No conditions needed fixing.")

if __name__ == "__main__":
    fix_buckets()
