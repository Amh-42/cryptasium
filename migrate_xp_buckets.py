from app import create_app
from models import db, User, CustomRank, RankCondition, TrackableEntry, TaskCompletion

def migrate():
    app = create_app()
    with app.app_context():
        print("Starting XP Buckets migration...")
        
        users = User.query.all()
        for user in users:
            print(f"Processing user: {user.username}")
            
            # 1. Find the "primary" Total XP condition (or create one if needed? No, migrate existing)
            # We look for ANY total_xp condition.
            # Actually, we should check ALL ranks? 
            # Or usually the user has a "Current" or "Next" rank.
            # But conditions are per-rank. The "Bucket" concept applies to a specific condition on a specific rank.
            # Wait, if I complete a task, it generates XP. This XP counts towards ALL ranks?
            # Currently: `user.get_total_xp()` counts ALL entries.
            # `RankCondition(total_xp)` checks `user.get_total_xp()`.
            # If we make `total_xp` conditions into "Buckets", they ONLY count allocated entries.
            # So, if we have 5 Ranks, each with a "Total XP" condition, do we need to duplicate the Entry 5 times?
            # NO! `Total XP` usually implies "Global Lifetime XP".
            # If the user wants "Buckets", they likely mean "Category XP" or specific "Level XP".
            # BUT the user said: "if there is at leaset two or more ... for the next level up ... prompt".
            # This implies the bucket is relevant for the *Next Level Up*.
            # If I assign an entry to Condition A (Rank 2), does it count for Rank 3?
            # If Condition A is "Total XP" bucket, it sums allocated entries.
            # If Rank 3 has Condition B ("Total XP" bucket), it sums allocated entries for B.
            # So if I allocate to A, B doesn't see it.
            # This creates "Local Level XP" instead of "Global Cumulative XP".
            # Is this what the user wants? "add new condition with xp that new one should be 0 and the already existing condition must take the total xp".
            # YES. This implies "Prestige/Level-specific XP" or distinct pools.
            # So, we need to assign existing XP to the *Current Active Rank's* condition? 
            # Or to ALL existing Total XP conditions?
            # If I assign to Condition A, and Condition B is separate, Condition B is 0.
            # User wants "existing condition must take the total xp".
            # This implies we should find ALL existing "Total XP" conditions and assign existing XP to them?
            # No, an entry has only ONE `allocated_condition_id`.
            # We can't allocate one entry to multiple buckets.
            # Unless we don't allocated, and rely on "Global".
            # But the user wants "New one = 0".
            # This implies we MUST allocate to specific IDs.
            # Dilemma: One entry cannot satisfy two buckets if buckets are exclusive.
            # Resolution: The user likely wants *One* Main Global Bucket that carries over? 
            # Or maybe they accept that XP is spent/reset?
            # Let's assume the user has multiple conditions on the *Same* Rank (e.g. "Main XP" and "Bonus XP").
            # They want existing XP to go to "Main XP".
            # For other ranks? If Rank 3 has "Main XP", does it inherit?
            # If `is_bucket` is True, it sums `allocated_condition_id == self.id`.
            # So it does NOT inherit from other IDs.
            # This implies strict separation.
            # So if I check Rank 3, I need new XP for Rank 3?
            # This effectively resets XP per rank?
            # If so, that's a huge change.
            # However, `user.get_total_xp()` is legacy.
            # The prompt says: "already existing condition must take the total xp".
            # I will assume we allocate to the *highest level* or *current next rank* conditions?
            # Or maybe we just allocate to the *first found* condition and assume the user understands?
            # Let's target the *Next Rank* (or all valid ranks).
            # Actually, better approach:
            # We cannot clone entries. We can only set `allocated_condition_id` once.
            # If we set it to Condition X, then Condition Y sees 0.
            # User said "already existing condition must take the total xp".
            # This implies "Condition X" (existing) gets it. "Condition Y" (new) gets 0.
            # This works for the *Same Rank*.
            # What about *Across Ranks*?
            # If Rank 2 has Cond A, Rank 3 has Cond B.
            # If we allocate to A, B sees 0.
            # Unless B is *also* global?
            # If B is `is_bucket=False` (default), it sees global XP (including allocations? We changed logic to sum trackable_xp + task_xp).
            # Wait, `get_total_xp()` sums ALL entries regardless of allocation?
            # `user.get_total_xp()`:
            #   `sum(e.count * xp for e in entries)` -> iterates all entries.
            #   It does NOT filter by allocation.
            #   So `is_bucket=False` (Global) sees EVERYTHING.
            #   `is_bucket=True` (Bucket) sees ONLY allocated.
            # Solution:
            #   - Mark the "Existing" condition as `is_bucket=False` (Keep it Global)?
            #   - Mark the "New" condition as `is_bucket=True` (Start at 0).
            #   - BUT user said "Existing condition must take the total xp".
            #   - If existing is global, it takes total.
            #   - If new is bucket, it takes 0 (initially).
            #   - When we add NEW XP, if we allocate to Existing (Global), New (Bucket) sees nothing.
            #   - If we allocate to New (Bucket), does Global see it?
            #   - `user.get_total_xp()` sums all entries. So yes, Global sees it!
            #   - This works perfectly!
            #   - We don't need to migrate entries to `allocated_id`.
            #   - We just need to ensure the "New" condition is a Bucket, and the "Old" one stays Global.
            #   - BUT `RankCondition.check_condition` for Global (`is_bucket=False`) uses `user.get_total_xp()`.
            #   - This works.
            #   - User's issue: "currently... currently equal ... added to all of them".
            #   - This happens because *both* were Global.
            #   - We need to make *at least one* (or both?) Buckets to separate them.
            #   - If we make *Both* buckets?
            #   - Then we MUST allocate existing entries to one of them.
            #   - If we allocate to A, B sees 0.
            #   - This separates them.
            #   - Does Global `get_total_xp()` still work? Yes, it ignores allocation ID.
            #   - So Global Stats on dashboard (Header) will still show correct Total.
            #   - But Rank Conditions will be separated.
            #   - This is exactly what is needed.
            #   - Implementation:
            #       - Convert ALL "Total XP" conditions to `is_bucket=True`.
            #       - Assign ALL existing `TrackableEntry` and `TaskCompletion` (with `allocated_id` is None) to the *First* Condition of the *Highest Unlocked Rank*? Or just the first one we find?
            #       - User said: "added to the first total xp condition".
            #       - I'll find the *Next Rank* (target).
            #       - Find its first total_xp condition.
            #       - Allocate all unallocated XP to it.
            #       - What about previous ranks? If they are passed, who cares?
            #       - What about future ranks? They will start at 0?
            #       - If future ranks use "Total XP" condition, and we bucketize it, they will start at 0.
            #       - This effectively makes ranks "Prestige" (resetting).
            #       - If the user wants "Global Milestone" (e.g. 10k XP Total), they should use `is_bucket=False`.
            #       - But they asked for separation.
            #       - I will proceed with: **Only bucketize conditions on the Current/Next Rank?**
            #       - No, that's messy.
            #       - User said "Level 4 rank has 4 conditions with all of them being xp ... it addes them to all".
            #       - So for *that specific rank*, they want separation.
            #       - I will migrate: Find all ranks. For each rank, if it has `total_xp` conditions:
            #           - Set them all to `is_bucket=True`.
            #           - Allocate historical entries to the *First* one of the *Current Active/Next Rank*?
            #           - Or allocate to the *First one of Every Rank*? (Impossible, 1:1 relation).
            #           - Allocate to the *First one of the First Rank*?
            #           - If I Allocate to Rank 1 Cond A:
            #               - Rank 1 Cond A = Full XP.
            #               - Rank 2 Cond B = 0 XP.
            #               - Rank 3 Cond C = 0 XP.
            #           - This seems correctly "Bucketized".
            #           - **CRITICAL**: If I do this, users lose progress on Rank 2/3 if it was based on Total XP.
            #           - Unless they want that? "new one should be 0".
            #           - I'll assume they want separation.
            #           - But wait, "Total XP" usually implies cumulative.
            #           - Maybe I should only bucketize conditions if there are *multiple* on the same rank?
            #           - "if there is at leaset two or more ... prompt".
            #           - Strategy:
            #               1. Iterate all Ranks.
            #               2. Group `total_xp` conditions.
            #               3. If count > 1:
            #                   - Set ALL to `is_bucket=True`.
            #                   - If they were `total_xp` (Global), migrate existing unallocated entries to the *First* one of this group.
            #                   - (Wait, if I have Rank 1 (Multiple) and Rank 2 (Multiple), I can't satisfy both).
            #                   - Assuming efficient user: Likely modifying the *Next* rank (active goal).
            #                   - I will prioritize the *Next Rank* (Current incomplete rank).
            #                   - Find Next Rank. If it has multiple XP conditions, bucketize them and assign unallocated XP to the first.
            
            # Refined Plan for Script:
            # 1. Get user. `get_user_stats()` -> find `next_rank`.
            # 2. If `next_rank` exists:
            # 3. Get `total_xp` conditions for `next_rank`.
            # 4. If len > 0:
            #    - Set ALL to `is_bucket=True`.
            #    - Pick `conditions[0]` as "Default Old Bucket".
            #    - Update `TrackableEntry.query.filter_by(user_id=user.id, allocated_condition_id=None).update({allocated_condition_id: default.id})`.
            #    - DO same for `TaskCompletion`.
            # 5. Commit.
            
            # This handles the immediate issue for the active goal.
            # Future/Past ranks? We leave them (if single, they stay Global).
            pass
            
            # stats = create_app().get_user_stats_for_user(user) # Need to expose this or simulate it
            # Simulate get_user_stats logic briefly to find next rank
            total_xp = user.get_total_xp()
            trackable_entries = user.trackable_entries
            
            # Simple Next Rank Finder
            # Ranks ordered by level. Find first one where check_conditions_met is False.
            ranks = CustomRank.query.filter_by(user_id=user.id).order_by(CustomRank.level).all()
            next_rank = None
            for rank in ranks:
                met, _ = rank.check_conditions_met(user.id)
                if not met:
                    next_rank = rank
                    break
            
            if next_rank:
                print(f"Targeting active goal rank: {next_rank.name}")
                xp_conditions = [c for c in next_rank.conditions if c.condition_type == 'total_xp']
                
                # If there are XP conditions, we migrate to the first one to enable bucketing
                if xp_conditions:
                    print(f"Found {len(xp_conditions)} XP conditions. Migrating to buckets...")
                    
                    # 1. Set all to buckets
                    for c in xp_conditions:
                        c.is_bucket = True
                    
                    # 2. Allocate existing unallocated entries to the first one
                    target_bucket = xp_conditions[0]
                    
                    # TrackableEntry
                    t_count = TrackableEntry.query.filter_by(
                        user_id=user.id, 
                        allocated_condition_id=None
                    ).update(
                        {'allocated_condition_id': target_bucket.id},
                        synchronize_session=False
                    )
                    
                    # TaskCompletion
                    c_count = TaskCompletion.query.filter_by(
                        user_id=user.id, 
                        allocated_condition_id=None
                    ).update(
                        {'allocated_condition_id': target_bucket.id},
                        synchronize_session=False
                    )
                    
                    print(f"Allocated {t_count} entries and {c_count} completions to condition '{target_bucket.custom_name or 'Total XP'}' (ID: {target_bucket.id})")
                    db.session.commit()
            else:
                 print("No next rank found / All ranks met.")

if __name__ == '__main__':
    migrate()
