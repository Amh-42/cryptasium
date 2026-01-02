"""
Database models for Cryptasium application
Fully Dynamic Gamification System - All configuration stored in database
"""
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()


# ========== USER MODEL ==========

class User(UserMixin, db.Model):
    """User model for authentication and multi-tenancy"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Profile customization
    avatar_url = db.Column(db.String(500))
    display_name = db.Column(db.String(100))
    timezone = db.Column(db.String(50), default='UTC')
    
    # YouTube sync data
    youtube_subscribers = db.Column(db.Integer, default=0)
    youtube_channel_views = db.Column(db.Integer, default=0)
    last_youtube_sync = db.Column(db.DateTime)
    
    # Relationships - Dynamic Gamification
    trackable_types = db.relationship('TrackableType', backref='user', lazy=True, cascade='all, delete-orphan')
    trackable_entries = db.relationship('TrackableEntry', backref='user', lazy=True, cascade='all, delete-orphan')
    custom_ranks = db.relationship('CustomRank', backref='user', lazy=True, cascade='all, delete-orphan')
    daily_tasks = db.relationship('UserDailyTask', backref='user', lazy=True, cascade='all, delete-orphan')
    task_completions = db.relationship('TaskCompletion', backref='user', lazy=True, cascade='all, delete-orphan')
    achievements = db.relationship('Achievement', backref='user', lazy=True, cascade='all, delete-orphan')
    user_achievements = db.relationship('UserAchievement', backref='user', lazy=True, cascade='all, delete-orphan')
    streaks = db.relationship('Streak', backref='user', lazy=True, cascade='all, delete-orphan')
    daily_logs = db.relationship('DailyLog', backref='user', lazy=True, cascade='all, delete-orphan')
    user_settings = db.relationship('UserSettings', backref='user', lazy=True, uselist=False, cascade='all, delete-orphan')
    dashboard_images = db.relationship('DashboardImage', backref='user', lazy=True, cascade='all, delete-orphan')
    
    # Legacy relationships (kept for backward compatibility)
    blog_posts = db.relationship('BlogPost', backref='user', lazy=True)
    videos = db.relationship('YouTubeVideo', backref='user', lazy=True)
    shorts = db.relationship('Short', backref='user', lazy=True)
    podcasts = db.relationship('Podcast', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def get_total_xp(self):
        """Calculate total XP from all sources"""
        total = 0
        for entry in self.trackable_entries:
            if entry.trackable_type:
                total += entry.count * entry.trackable_type.xp_per_unit
        # Add daily task XP
        for log in self.daily_logs:
            total += log.total_xp or 0
            
        # Add dynamic YouTube XP if enabled
        if self.user_settings and self.user_settings.enable_youtube_sync:
            total += self.get_youtube_xp()
        
        return total

    def get_youtube_xp(self):
        """Calculate dynamic XP from synced YouTube data if enabled"""
        # Check if YouTube sync is enabled in settings
        if not self.user_settings or not self.user_settings.enable_youtube_sync:
            return 0
            
        xp = 0.0
        
        # 1 subscriber = 20 points
        xp += (self.youtube_subscribers or 0) * 20
        
        # 1 view = 0.5 points (using channel views)
        xp += (self.youtube_channel_views or 0) * 0.5
        
        # Videos based on duration
        # Shorts (< 1 min) = 100 points
        # Short Longs (< 3 min) = 200 points
        # Mid Longs (< 8 min) = 400 points
        # Long videos (>= 8 min) = 800 points
        
        # Check YouTubeVideo model (longs potentially contains some shorts too)
        for video in self.videos:
            dur = video.duration_seconds or 0
            if video.content_type == 'shorts' or dur < 60:
                xp += 100
            elif dur < 180:
                xp += 200
            elif dur < 480:
                xp += 400
            else:
                xp += 800
                
        # Check Short model
        for short in self.shorts:
            # These are by definition shorts
            xp += 100
            
        return int(xp)
    
    def get_current_rank(self):
        """Get user's current rank based on XP"""
        total_xp = self.get_total_xp()
        ranks = CustomRank.query.filter_by(user_id=self.id).order_by(CustomRank.min_xp.desc()).all()
        for rank in ranks:
            if total_xp >= rank.min_xp:
                return rank
        # Return a default if no ranks defined
        return None
    
    def __repr__(self):
        return f'<User {self.username}>'


# ========== DYNAMIC GAMIFICATION SYSTEM ==========

class TrackableType(db.Model):
    """
    User-defined trackable types. Each user can create their own types.
    Examples: "Blog Posts", "YouTube Videos", "Shorts", "Blue Package", "Client Call", "Sales", etc.
    """
    __tablename__ = 'trackable_types'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Definition
    name = db.Column(db.String(100), nullable=False)  # "Blog Post", "YouTube Short", "Sale", etc.
    slug = db.Column(db.String(100), nullable=False)  # "blog_post", "youtube_short", "sale"
    description = db.Column(db.String(500))
    category = db.Column(db.String(50), default='content')  # 'content', 'task', 'metric', 'sales', 'finance'
    
    # Gamification - XP calculation modes
    xp_per_unit = db.Column(db.Integer, default=10)  # Base XP earned per item
    xp_mode = db.Column(db.String(20), default='fixed')  # 'fixed', 'value_based', 'tiered'
    # For 'value_based': XP = value * xp_multiplier (e.g., $100 sale * 0.5 = 50 XP)
    xp_multiplier = db.Column(db.Float, default=1.0)
    # For 'tiered': Different XP for different tiers (stored in tiers_config JSON)
    tiers_config = db.Column(db.Text)  # JSON: [{"name": "Bronze", "min": 0, "xp": 10}, {"name": "Silver", "min": 100, "xp": 50}]
    
    # Value tracking (for sales, income, expenses)
    track_value = db.Column(db.Boolean, default=False)  # Track monetary/numeric value?
    value_label = db.Column(db.String(50), default='Value')  # "Price", "Amount", "Revenue", etc.
    value_prefix = db.Column(db.String(10), default='$')  # Currency symbol or unit
    value_suffix = db.Column(db.String(10), default='')  # e.g., "hrs", "units"
    
    # Visual
    icon = db.Column(db.String(50), default='ph-star')  # Phosphor icon name
    color = db.Column(db.String(20), default='#0ea5e9')  # Hex color
    emoji = db.Column(db.String(10))  # Optional emoji
    
    # Behavior
    is_countable = db.Column(db.Boolean, default=True)  # Can you count multiple?
    track_duration = db.Column(db.Boolean, default=False)  # Track time/duration?
    track_views = db.Column(db.Boolean, default=False)  # Track views?
    allows_negative = db.Column(db.Boolean, default=False)  # Allow negative values (for expenses)?
    
    # Goals
    daily_goal = db.Column(db.Integer, default=0)  # Daily target (0 = no goal)
    weekly_goal = db.Column(db.Integer, default=0)  # Weekly target
    monthly_goal = db.Column(db.Integer, default=0)  # Monthly target
    value_goal = db.Column(db.Float, default=0)  # Value-based goal (e.g., $1000 in sales)
    
    # Ordering & Status
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_pinned = db.Column(db.Boolean, default=False)  # Show on dashboard
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    entries = db.relationship('TrackableEntry', backref='trackable_type', lazy=True, cascade='all, delete-orphan')
    
    def get_tiers(self):
        """Get tier configuration"""
        try:
            return json.loads(self.tiers_config or '[]')
        except:
            return []
    
    def set_tiers(self, tiers_list):
        """Set tier configuration"""
        self.tiers_config = json.dumps(tiers_list)
    
    def get_total_count(self):
        """Get total count of all entries for this type"""
        return sum(e.count for e in self.entries)
    
    def get_total_value(self):
        """Get total value of all entries (for sales/income/expense tracking)"""
        return sum(e.value or 0 for e in self.entries)
    
    def get_count_for_period(self, start_date, end_date):
        """Get count for a specific date range"""
        return sum(
            e.count for e in self.entries 
            if e.date >= start_date and e.date <= end_date
        )
    
    def get_value_for_period(self, start_date, end_date):
        """Get total value for a specific date range"""
        return sum(
            e.value or 0 for e in self.entries 
            if e.date >= start_date and e.date <= end_date
        )
    
    def calculate_xp_for_entry(self, count=1, value=0):
        """Calculate XP for an entry based on the XP mode"""
        if self.xp_mode == 'fixed':
            return count * self.xp_per_unit
        elif self.xp_mode == 'value_based' and value:
            # XP based on the value (e.g., sales amount)
            return int(abs(value) * (self.xp_multiplier or 1.0))
        elif self.xp_mode == 'tiered' and value:
            # XP based on value tiers
            tiers = self.get_tiers()
            xp = self.xp_per_unit  # Default
            for tier in sorted(tiers, key=lambda t: t.get('min', 0), reverse=True):
                if abs(value) >= tier.get('min', 0):
                    xp = tier.get('xp', self.xp_per_unit)
                    break
            return xp * count
        return count * self.xp_per_unit
    
    def get_total_xp(self):
        """Calculate total XP earned from this type"""
        return sum(e.get_xp() for e in self.entries)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'category': self.category,
            'xp_per_unit': self.xp_per_unit,
            'icon': self.icon,
            'color': self.color,
            'emoji': self.emoji,
            'daily_goal': self.daily_goal,
            'weekly_goal': self.weekly_goal,
            'monthly_goal': self.monthly_goal,
            'is_pinned': self.is_pinned,
            'total_count': self.get_total_count(),
            'total_xp': self.get_total_xp()
        }
    
    def __repr__(self):
        return f'<TrackableType {self.name}>'


class TrackableEntry(db.Model):
    """
    Individual entries for tracked items.
    Each time a user completes a trackable, an entry is created.
    """
    __tablename__ = 'trackable_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    trackable_type_id = db.Column(db.Integer, db.ForeignKey('trackable_types.id'), nullable=False, index=True)
    
    # Entry details
    date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    count = db.Column(db.Integer, default=1)  # How many (usually 1)
    
    # Value tracking (for sales, income, expenses)
    value = db.Column(db.Float, default=0)  # Monetary or numeric value
    
    # Optional metadata
    title = db.Column(db.String(300))  # Optional title/description
    notes = db.Column(db.Text)
    url = db.Column(db.String(500))  # Link to the content
    
    # Extended tracking (if enabled on type)
    duration_minutes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    
    # For tiered/categorized entries (e.g., "Bronze Package", "Gold Package")
    tier_name = db.Column(db.String(50))
    
    # Manual allocation to rank conditions (buckets)
    allocated_condition_id = db.Column(db.Integer, db.ForeignKey('rank_conditions.id'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_xp(self):
        """Calculate XP for this entry based on the trackable type's XP mode"""
        if self.trackable_type:
            return self.trackable_type.calculate_xp_for_entry(self.count, self.value)
        return 0
    
    def __repr__(self):
        return f'<TrackableEntry {self.trackable_type.name if self.trackable_type else "?"} x{self.count}>'


class CustomRank(db.Model):
    """
    User-defined rank/level system.
    Users can create their own ranks with custom names, XP thresholds, and visuals.
    Supports both legacy XP-only mode and new multi-condition mode.
    """
    __tablename__ = 'custom_ranks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Rank definition
    level = db.Column(db.Integer, nullable=False, default=1)  # Numeric level
    name = db.Column(db.String(100), nullable=False)  # "Beginner", "Expert", etc.
    code = db.Column(db.String(10))  # Short code like "BT", "MS"
    description = db.Column(db.String(500))
    
    # Requirements (legacy - kept for backward compatibility)
    min_xp = db.Column(db.Integer, nullable=True)  # XP needed to reach this rank (nullable for multi-condition ranks)
    
    # Visuals
    icon = db.Column(db.String(100))  # Icon path or phosphor icon
    color = db.Column(db.String(20), default='#666666')
    badge_image = db.Column(db.String(500))  # Path to badge image
    
    # Special flags
    is_max_rank = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conditions = db.relationship('RankCondition', backref='rank', lazy=True, cascade='all, delete-orphan')
    
    def check_conditions_met(self, user_id):
        """
        Check if all conditions for this rank are met.
        Returns (is_met: bool, progress: dict)
        """
        # If no conditions defined, fall back to legacy XP-only mode
        if not self.conditions:
            if self.min_xp is not None:
                user = User.query.get(user_id)
                total_xp = user.get_total_xp() if user else 0
                return total_xp >= self.min_xp, {
                    'legacy_xp': {
                        'type': 'total_xp',
                        'threshold': self.min_xp,
                        'current': total_xp,
                        'met': total_xp >= self.min_xp,
                        'custom_name': 'Total XP'
                    }
                }
            return True, {}  # No conditions = always met
        
        # Check all conditions (AND logic)
        all_met = True
        progress = {}
        
        for condition in self.conditions:
            is_met, current_value = condition.check_condition(user_id)
            progress[condition.id] = {
                'type': condition.condition_type,
                'threshold': condition.threshold,
                'current': current_value,
                'met': is_met,
                'custom_name': condition.custom_name,
                'trackable_slug': condition.trackable_slug
            }
            if not is_met:
                all_met = False
        
        return all_met, progress
    
    def to_dict(self):
        return {
            'id': self.id,
            'level': self.level,
            'name': self.name,
            'code': self.code,
            'min_xp': self.min_xp,
            'icon': self.icon,
            'color': self.color,
            'badge_image': self.badge_image,
            'is_max_rank': self.is_max_rank,
            'condition_count': len(self.conditions)
        }
    
    def __repr__(self):
        return f'<CustomRank L{self.level}: {self.name}>'


class RankCondition(db.Model):
    """
    Individual conditions that must be met to unlock a rank.
    Multiple conditions can be attached to a single rank (AND logic).
    """
    __tablename__ = 'rank_conditions'
    
    id = db.Column(db.Integer, primary_key=True)
    rank_id = db.Column(db.Integer, db.ForeignKey('custom_ranks.id'), nullable=False, index=True)
    
    # Condition definition
    condition_type = db.Column(db.String(50), nullable=False)  # See CONDITION_TYPES below
    threshold = db.Column(db.Integer, nullable=False)  # The value that must be reached
    custom_name = db.Column(db.String(100))  # User-defined name for this condition
    is_bucket = db.Column(db.Boolean, default=False)  # If True, only allocated entries count
    
    # Optional: for trackable-specific conditions
    trackable_slug = db.Column(db.String(100))  # Used when condition_type is 'trackable_xp' or 'trackable_count'
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Condition types supported:
    # - 'total_xp': Total XP across all trackables
    # - 'trackable_xp': XP from a specific trackable
    # - 'trackable_count': Count for a specific trackable
    # - 'youtube_subscribers': YouTube subscriber count
    # - 'youtube_total_views': Total YouTube channel views
    # - 'youtube_long_count': Number of long-form videos
    # - 'youtube_short_count': Number of shorts
    # - 'youtube_long_views': Total views on long videos
    # - 'youtube_short_views': Total views on shorts
    # - 'streak_current': Current daily streak
    # - 'streak_longest': Longest streak achieved
    # - 'tasks_completed': Total daily tasks completed
    # - 'perfect_weeks': Number of perfect weeks
    # - 'achievements_unlocked': Total achievements earned
    
    def check_condition(self, user_id):
        """
        Check if this condition is met for the given user.
        Returns (is_met: bool, current_value: int)
        """
        from datetime import timedelta
        
        user = User.query.get(user_id)
        if not user:
            return False, 0
        
        current_value = 0
        
        # Total XP
        if self.condition_type == 'total_xp':
            if self.is_bucket:
                # Sum entries specifically allocated to this condition (bucket)
                # Filter by user_id through the relationship
                entries = TrackableEntry.query.filter_by(
                    user_id=user_id,
                    allocated_condition_id=self.id
                ).all()
                current_value = sum(entry.get_xp() for entry in entries)
            else:
                current_value = user.get_total_xp()
        
        # Trackable-specific XP
        elif self.condition_type == 'trackable_xp' and self.trackable_slug:
            trackable = TrackableType.query.filter_by(
                user_id=user_id,
                slug=self.trackable_slug
            ).first()
            if trackable:
                current_value = trackable.get_total_xp()
        
        # Trackable-specific count
        elif self.condition_type == 'trackable_count' and self.trackable_slug:
            trackable = TrackableType.query.filter_by(
                user_id=user_id,
                slug=self.trackable_slug
            ).first()
            if trackable:
                current_value = trackable.get_total_count()
        
        # YouTube subscribers
        elif self.condition_type == 'youtube_subscribers':
            current_value = user.youtube_subscribers or 0
        
        # YouTube total views
        elif self.condition_type == 'youtube_total_views':
            # Sum all views from YouTubeVideo and Short models
            from sqlalchemy import func
            long_views = db.session.query(func.sum(YouTubeVideo.views)).filter_by(user_id=user_id).scalar() or 0
            short_views = db.session.query(func.sum(Short.views)).filter_by(user_id=user_id).scalar() or 0
            current_value = long_views + short_views
        
        # YouTube long video count
        elif self.condition_type == 'youtube_long_count':
            current_value = YouTubeVideo.query.filter_by(user_id=user_id).count()
        
        # YouTube short count
        elif self.condition_type == 'youtube_short_count':
            current_value = Short.query.filter_by(user_id=user_id).count()
        
        # YouTube long video views
        elif self.condition_type == 'youtube_long_views':
            from sqlalchemy import func
            current_value = db.session.query(func.sum(YouTubeVideo.views)).filter_by(user_id=user_id).scalar() or 0
        
        # YouTube short views
        elif self.condition_type == 'youtube_short_views':
            from sqlalchemy import func
            current_value = db.session.query(func.sum(Short.views)).filter_by(user_id=user_id).scalar() or 0
        
        # Current streak
        elif self.condition_type == 'streak_current':
            streak = Streak.query.filter_by(
                user_id=user_id,
                streak_type='daily_xp'
            ).first()
            current_value = streak.current_count if streak else 0
        
        # Longest streak
        elif self.condition_type == 'streak_longest':
            streak = Streak.query.filter_by(
                user_id=user_id,
                streak_type='daily_xp'
            ).first()
            current_value = streak.longest_count if streak else 0
        
        # Total tasks completed
        elif self.condition_type == 'tasks_completed':
            current_value = TaskCompletion.query.filter_by(user_id=user_id).count()
        
        # Total days active
        elif self.condition_type == 'total_days_active':
            from sqlalchemy import func
            current_value = db.session.query(func.count(func.distinct(func.date(TrackableEntry.created_at))))\
                .filter_by(user_id=user_id).scalar() or 0
                
        # Total goals met
        elif self.condition_type == 'total_goals_met':
            current_value = DailyLog.query.filter_by(user_id=user_id, goal_met=True).count()
            
        # YouTube total videos (long + shorts)
        elif self.condition_type == 'youtube_total_count':
            long_count = YouTubeVideo.query.filter_by(user_id=user_id).count()
            short_count = Short.query.filter_by(user_id=user_id).count()
            current_value = long_count + short_count

        # Perfect weeks
        elif self.condition_type == 'perfect_weeks':
            # Count weeks where all 7 days had goal_met = True
            # This is a simplified version - could be more sophisticated
            logs = DailyLog.query.filter_by(user_id=user_id, goal_met=True).all()
            # Group by week and count weeks with 7+ days
            from collections import defaultdict
            weeks = defaultdict(int)
            for log in logs:
                week_key = log.date.isocalendar()[:2]  # (year, week_number)
                weeks[week_key] += 1
            current_value = sum(1 for count in weeks.values() if count >= 7)
        
        # Achievements unlocked
        elif self.condition_type == 'achievements_unlocked':
            current_value = UserAchievement.query.filter_by(user_id=user_id).count()
        
        return current_value >= self.threshold, current_value
    
    def to_dict(self):
        return {
            'id': self.id,
            'rank_id': self.rank_id,
            'condition_type': self.condition_type,
            'threshold': self.threshold,
            'trackable_slug': self.trackable_slug,
            'custom_name': self.custom_name
        }
    
    def __repr__(self):
        return f'<RankCondition {self.condition_type}: {self.threshold}>'


class UserDailyTask(db.Model):
    """
    User-defined tasks for XP with flexible repeat schedules and task types.
    Supports: repeating tasks, one-time tasks, count-based tasks, and spaced repetition.
    """
    __tablename__ = 'user_daily_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Task definition
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    
    # Task Type: 'normal' (complete once per period), 'count' (complete X times)
    task_type = db.Column(db.String(20), default='normal')  # 'normal', 'count'
    target_count = db.Column(db.Integer, default=1)  # For count tasks: how many times to complete
    
    # Repeat Schedule
    # 'none', 'daily', 'weekly', 'monthly', 'yearly', 'weekdays', 'weekends',
    # 'custom' (every X units), 'ebbinghaus' (spaced repetition), 'once' (one-time task), 'unlimited'
    repeat_type = db.Column(db.String(20), default='daily')
    
    # Custom repeat settings
    repeat_interval = db.Column(db.Integer, default=1)  # For 'custom': every X units
    repeat_unit = db.Column(db.String(10), default='day')  # 'day', 'week', 'month'
    repeat_days = db.Column(db.String(50))  # For 'weekly': JSON array like "[1,3,5]" for Mon/Wed/Fri
    repeat_day_of_month = db.Column(db.Integer)  # For 'monthly': which day (1-31)
    
    # One-time task settings
    due_date = db.Column(db.Date)  # For 'once' tasks: when it's due
    completed_date = db.Column(db.Date)  # For 'once' tasks: when completed
    
    # Ebbinghaus spaced repetition settings
    ebbinghaus_level = db.Column(db.Integer, default=0)  # Current level in spaced repetition
    next_due_date = db.Column(db.Date)  # When the task is next due
    
    # Gamification
    xp_value = db.Column(db.Integer, default=10)
    xp_per_count = db.Column(db.Integer, default=0)  # For count tasks: XP per completion (0 = only on full completion)
    streak_bonus = db.Column(db.Boolean, default=True)  # Eligible for streak bonuses
    
    # Visual
    icon = db.Column(db.String(50), default='ph-check-circle')
    color = db.Column(db.String(20), default='#10b981')
    emoji = db.Column(db.String(10))
    
    # Ordering & Status
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_pinned = db.Column(db.Boolean, default=False)
    
    # Category for organization
    category = db.Column(db.String(50), default='general')  # 'health', 'work', 'learning', 'habits', 'general'
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to task completions
    completions = db.relationship('TaskCompletion', backref='task', lazy=True, cascade='all, delete-orphan')
    
    def get_repeat_days(self):
        """Get repeat days as a list"""
        try:
            return json.loads(self.repeat_days or '[]')
        except:
            return []
    
    def set_repeat_days(self, days):
        """Set repeat days from a list"""
        self.repeat_days = json.dumps(days)
    
    def is_due_today(self, today=None):
        """Check if this task is due today based on its repeat schedule"""
        today = today or date.today()
        
        if self.repeat_type == 'none':
            # No deadline task - shows until completed, then archived
            return not self.completed_date
        
        if self.repeat_type == 'once':
            # One-time task: due if not completed and due_date is today or past
            if self.completed_date:
                return False
            return self.due_date is None or self.due_date <= today
        
        if self.repeat_type == 'daily':
            return True
        
        if self.repeat_type == 'unlimited':
            return True
        
        if self.repeat_type == 'weekdays':
            return today.weekday() < 5  # Mon=0 to Fri=4
        
        if self.repeat_type == 'weekends':
            return today.weekday() >= 5  # Sat=5, Sun=6
        
        if self.repeat_type == 'weekly':
            days = self.get_repeat_days()
            return today.weekday() in days
        
        if self.repeat_type == 'monthly':
            return today.day == (self.repeat_day_of_month or 1)
        
        if self.repeat_type == 'yearly':
            # Check if today matches the original creation date's month/day
            return today.month == self.created_at.month and today.day == self.created_at.day
        
        if self.repeat_type == 'custom':
            # Every X units from creation (day, week, month)
            if not self.created_at:
                return True
            
            unit = self.repeat_unit or 'day'
            interval = self.repeat_interval or 1
            
            if unit == 'day':
                days_since = (today - self.created_at.date()).days
                return days_since % interval == 0
            elif unit == 'week':
                weeks_since = (today - self.created_at.date()).days // 7
                # Also check if it's the same weekday
                return weeks_since % interval == 0 and today.weekday() == self.created_at.weekday()
            elif unit == 'month':
                months_since = (today.year - self.created_at.year) * 12 + (today.month - self.created_at.month)
                return months_since % interval == 0 and today.day == self.created_at.day
            
            return True
        
        if self.repeat_type == 'ebbinghaus':
            # Spaced repetition: due on next_due_date
            return self.next_due_date is None or self.next_due_date <= today
        
        return True
    
    def calculate_next_ebbinghaus_date(self):
        """Calculate next due date using Ebbinghaus spaced repetition intervals"""
        # Standard Ebbinghaus intervals: 1, 2, 4, 7, 15, 30, 60, 120 days
        intervals = [1, 2, 4, 7, 15, 30, 60, 120]
        level = min(self.ebbinghaus_level, len(intervals) - 1)
        self.next_due_date = date.today() + timedelta(days=intervals[level])
        self.ebbinghaus_level += 1
    
    def get_today_completion_count(self, today=None):
        """Get how many times this task was completed today"""
        today = today or date.today()
        return TaskCompletion.query.filter_by(
            task_id=self.id,
            date=today
        ).count()
    
    def is_completed_today(self, today=None):
        """Check if task is completed for today"""
        today = today or date.today()
        count = self.get_today_completion_count(today)
        if self.task_type == 'count':
            return count >= self.target_count
        return count > 0
    
    def __repr__(self):
        return f'<UserDailyTask {self.name}>'


class TaskCompletion(db.Model):
    """
    Tracks individual task completions.
    Allows multiple completions per day for count-based tasks.
    """
    __tablename__ = 'task_completions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey('user_daily_tasks.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    
    # For count tasks - track each completion
    count = db.Column(db.Integer, default=1)  # How many units completed in this entry
    notes = db.Column(db.String(500))
    
    # XP earned for this completion
    xp_earned = db.Column(db.Integer, default=0)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TaskCompletion {self.task_id} on {self.date}>'


class DailyLog(db.Model):
    """
    Daily log tracking task completion.
    Stores which tasks were completed each day.
    """
    __tablename__ = 'daily_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    
    # Completed tasks stored as JSON array of task IDs
    completed_tasks = db.Column(db.Text, default='[]')  # JSON array of task slugs
    
    # Calculated
    total_xp = db.Column(db.Integer, default=0)
    goal_met = db.Column(db.Boolean, default=False)
    
    # Notes
    notes = db.Column(db.Text)
    mood = db.Column(db.String(20))  # Optional mood tracking
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', name='unique_user_date'),
    )
    
    def get_completed_tasks(self):
        try:
            return json.loads(self.completed_tasks or '[]')
        except:
            return []
    
    def set_completed_tasks(self, tasks):
        self.completed_tasks = json.dumps(tasks)
    
    def calculate_xp(self, user_tasks):
        """Calculate XP based on completed tasks"""
        completed = self.get_completed_tasks()
        total = 0
        for task in user_tasks:
            if task.slug in completed:
                total += task.xp_value
        self.total_xp = total
        return total
    
    def __repr__(self):
        return f'<DailyLog {self.date}>'


class Achievement(db.Model):
    """
    User-defined achievements/badges.
    Users can create custom achievements with their own criteria.
    """
    __tablename__ = 'achievements'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Achievement definition
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    
    # Criteria (stored as JSON for flexibility)
    # Examples: {"type": "total_count", "trackable_slug": "blog_post", "threshold": 10}
    #           {"type": "streak", "min_days": 7}
    #           {"type": "xp_total", "threshold": 1000}
    criteria = db.Column(db.Text, default='{}')
    
    # Reward
    xp_reward = db.Column(db.Integer, default=100)
    
    # Visual
    icon = db.Column(db.String(50), default='ph-trophy')
    color = db.Column(db.String(20), default='#fbbf24')
    badge_image = db.Column(db.String(500))
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_hidden = db.Column(db.Boolean, default=False)  # Hidden until unlocked?
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_criteria(self):
        try:
            return json.loads(self.criteria or '{}')
        except:
            return {}
    
    def set_criteria(self, criteria_dict):
        self.criteria = json.dumps(criteria_dict)
    
    def __repr__(self):
        return f'<Achievement {self.name}>'


class UserAchievement(db.Model):
    """
    Tracks which achievements a user has unlocked.
    """
    __tablename__ = 'user_achievements'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievements.id'), nullable=False, index=True)
    
    # When unlocked
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Reference to achievement
    achievement = db.relationship('Achievement', backref='user_achievements')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'achievement_id', name='unique_user_achievement'),
    )
    
    def __repr__(self):
        return f'<UserAchievement {self.achievement_id}>'


class Streak(db.Model):
    """
    Tracks user streaks for various activities.
    """
    __tablename__ = 'streaks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Streak type
    streak_type = db.Column(db.String(50), nullable=False)  # 'daily_xp', 'weekly_perfect', etc.
    
    # Current state
    current_count = db.Column(db.Integer, default=0)
    longest_count = db.Column(db.Integer, default=0)
    
    # Dates
    last_activity_date = db.Column(db.Date)
    streak_start_date = db.Column(db.Date)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'streak_type', name='unique_user_streak_type'),
    )
    
    def update_streak(self, activity_date):
        """Update streak based on activity date"""
        if not self.last_activity_date:
            # First activity
            self.current_count = 1
            self.streak_start_date = activity_date
        elif activity_date == self.last_activity_date:
            # Same day, no change
            pass
        elif (activity_date - self.last_activity_date).days == 1:
            # Consecutive day
            self.current_count += 1
        elif (activity_date - self.last_activity_date).days > 1:
            # Streak broken
            self.current_count = 1
            self.streak_start_date = activity_date
        
        self.last_activity_date = activity_date
        
        if self.current_count > self.longest_count:
            self.longest_count = self.current_count
    
    def __repr__(self):
        return f'<Streak {self.streak_type}: {self.current_count}>'


class UserSettings(db.Model):
    """
    User-specific settings for gamification.
    """
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    
    # Appearance
    accent_color = db.Column(db.String(20), default='#e90e0e')
    
    # Points settings
    points_name = db.Column(db.String(20), default='XP')  # "XP", "Points", "Coins", etc.
    points_icon = db.Column(db.String(50), default='ph-lightning')
    
    # Daily goals
    daily_xp_goal = db.Column(db.Integer, default=50)
    
    # Bonuses
    perfect_day_bonus = db.Column(db.Integer, default=50)
    perfect_week_bonus = db.Column(db.Integer, default=500)
    streak_bonus_per_day = db.Column(db.Integer, default=5)  # Extra XP per streak day
    
    # Display preferences
    show_xp_animations = db.Column(db.Boolean, default=True)
    dark_mode = db.Column(db.Boolean, default=True)
    compact_view = db.Column(db.Boolean, default=False)
    show_dashboard_header = db.Column(db.Boolean, default=True)
    enable_youtube_sync = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserSettings {self.user_id}>'
    

class DashboardImage(db.Model):
    """
    Images uploaded by user for their dashboard header.
    """
    __tablename__ = 'dashboard_images'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    image_url = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DashboardImage {self.id}>'


# ========== LEGACY CONTENT MODELS (kept for backward compatibility) ==========

class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    excerpt = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)
    featured_image = db.Column(db.String(500))
    author = db.Column(db.String(100), default='Cryptasium Team')
    published = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)


class YouTubeVideo(db.Model):
    __tablename__ = 'youtube_videos'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    video_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    thumbnail_url = db.Column(db.String(500))
    duration = db.Column(db.String(20))
    duration_seconds = db.Column(db.Integer, default=0)
    content_type = db.Column(db.String(20), default='longs') 
    published = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)


class Podcast(db.Model):
    __tablename__ = 'podcasts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    episode_number = db.Column(db.Integer)
    audio_url = db.Column(db.String(500))
    thumbnail_url = db.Column(db.String(500))
    duration = db.Column(db.String(20))
    published = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)


class Short(db.Model):
    __tablename__ = 'shorts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    video_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    thumbnail_url = db.Column(db.String(500))
    duration = db.Column(db.String(20))
    published = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)


class CommunityPost(db.Model):
    __tablename__ = 'community_posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), default='Community Member')
    category = db.Column(db.String(50))
    published = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)


class TopicIdea(db.Model):
    __tablename__ = 'topic_ideas'
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    email = db.Column(db.String(200))
    name = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')
    reviewed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    reviewed_at = db.Column(db.DateTime)


# ========== LEGACY SYSTEM TABLES (kept for migrations) ==========

class SystemSettings(db.Model):
    """Global system settings stored in database"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get(key, default=None):
        setting = SystemSettings.query.filter_by(key=key).first()
        return setting.value if setting else default


class ContentCalendarEntry(db.Model):
    __tablename__ = 'content_calendar_entries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    scheduled_time = db.Column(db.Time)
    content_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='planned')
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_day = db.Column(db.Integer)
    color = db.Column(db.String(20), default='#0ea5e9')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    

# ========== HELPER FUNCTIONS ==========

def init_user_gamification(user_id):
    """
    Initialize default gamification settings for a new user.
    Creates default trackable types, ranks, and daily tasks.
    Includes content creation, sales, and finance tracking examples.
    """
    # Create user settings
    settings = UserSettings(user_id=user_id)
    db.session.add(settings)
    
    # Create default trackable types - Content Creation
    content_types = [
        {
            'name': 'Blog Post', 'slug': 'blog_post', 'icon': 'ph-article', 
            'color': '#3b82f6', 'xp_per_unit': 50, 'category': 'content',
            'description': 'Written blog articles and posts'
        },
        {
            'name': 'YouTube Video', 'slug': 'youtube_video', 'icon': 'ph-youtube-logo', 
            'color': '#ef4444', 'xp_per_unit': 100, 'category': 'content',
            'description': 'Long-form YouTube videos (8+ minutes)'
        },
        {
            'name': 'YouTube Short', 'slug': 'youtube_short', 'icon': 'ph-lightning', 
            'color': '#f97316', 'xp_per_unit': 25, 'category': 'content',
            'description': 'Short-form vertical videos (<60 seconds)'
        },
        {
            'name': 'Podcast Episode', 'slug': 'podcast', 'icon': 'ph-microphone', 
            'color': '#a855f7', 'xp_per_unit': 75, 'category': 'content',
            'description': 'Audio podcast episodes'
        },
    ]
    
    # Sales & Business Tracking Examples
    sales_types = [
        {
            'name': 'Sale', 'slug': 'sale', 'icon': 'ph-shopping-cart', 
            'color': '#22c55e', 'category': 'sales',
            'description': 'Track sales with value-based XP',
            'xp_mode': 'value_based', 'xp_multiplier': 0.1, 'xp_per_unit': 10,
            'track_value': True, 'value_label': 'Sale Amount', 'value_prefix': '$',
            'is_pinned': False
        },
        {
            'name': 'Client Call', 'slug': 'client_call', 'icon': 'ph-phone', 
            'color': '#0ea5e9', 'xp_per_unit': 15, 'category': 'sales',
            'description': 'Client calls and meetings',
            'is_pinned': False
        },
    ]
    
    # Finance Tracking Examples (not pinned by default)
    finance_types = [
        {
            'name': 'Income', 'slug': 'income', 'icon': 'ph-arrow-circle-up', 
            'color': '#22c55e', 'category': 'finance',
            'description': 'Track income received',
            'xp_mode': 'value_based', 'xp_multiplier': 0.05, 'xp_per_unit': 5,
            'track_value': True, 'value_label': 'Amount', 'value_prefix': '$',
            'is_pinned': False
        },
        {
            'name': 'Expense', 'slug': 'expense', 'icon': 'ph-arrow-circle-down', 
            'color': '#ef4444', 'category': 'finance',
            'description': 'Track expenses (no XP, just tracking)',
            'xp_per_unit': 0, 'xp_mode': 'fixed',
            'track_value': True, 'value_label': 'Amount', 'value_prefix': '$',
            'allows_negative': True, 'is_pinned': False
        },
    ]
    
    # Combine all default types
    all_types = content_types + sales_types + finance_types
    
    for i, t in enumerate(all_types):
        trackable = TrackableType(
            user_id=user_id,
            name=t['name'],
            slug=t['slug'],
            icon=t['icon'],
            color=t['color'],
            xp_per_unit=t.get('xp_per_unit', 10),
            xp_mode=t.get('xp_mode', 'fixed'),
            xp_multiplier=t.get('xp_multiplier', 1.0),
            category=t['category'],
            description=t.get('description', ''),
            track_value=t.get('track_value', False),
            value_label=t.get('value_label', 'Value'),
            value_prefix=t.get('value_prefix', '$'),
            allows_negative=t.get('allows_negative', False),
            display_order=i,
            is_pinned=t.get('is_pinned', True) if 'is_pinned' in t else (t['category'] == 'content')
        )
        db.session.add(trackable)
    
    # Create default ranks (more comprehensive progression)
    default_ranks = [
        {'level': 1, 'name': 'Newcomer', 'code': 'NC', 'min_xp': 0, 'color': '#6b7280', 'icon': 'ph-user'},
        {'level': 2, 'name': 'Beginner', 'code': 'BG', 'min_xp': 100, 'color': '#84cc16', 'icon': 'ph-plant'},
        {'level': 3, 'name': 'Learner', 'code': 'LR', 'min_xp': 300, 'color': '#22c55e', 'icon': 'ph-book-open'},
        {'level': 4, 'name': 'Apprentice', 'code': 'AP', 'min_xp': 750, 'color': '#14b8a6', 'icon': 'ph-graduation-cap'},
        {'level': 5, 'name': 'Skilled', 'code': 'SK', 'min_xp': 1500, 'color': '#06b6d4', 'icon': 'ph-wrench'},
        {'level': 6, 'name': 'Adept', 'code': 'AD', 'min_xp': 3000, 'color': '#0ea5e9', 'icon': 'ph-lightning'},
        {'level': 7, 'name': 'Expert', 'code': 'EX', 'min_xp': 5000, 'color': '#3b82f6', 'icon': 'ph-star'},
        {'level': 8, 'name': 'Specialist', 'code': 'SP', 'min_xp': 8000, 'color': '#6366f1', 'icon': 'ph-medal'},
        {'level': 9, 'name': 'Professional', 'code': 'PR', 'min_xp': 12000, 'color': '#8b5cf6', 'icon': 'ph-briefcase'},
        {'level': 10, 'name': 'Master', 'code': 'MS', 'min_xp': 18000, 'color': '#a855f7', 'icon': 'ph-crown'},
        {'level': 11, 'name': 'Grandmaster', 'code': 'GM', 'min_xp': 25000, 'color': '#d946ef', 'icon': 'ph-diamond'},
        {'level': 12, 'name': 'Champion', 'code': 'CH', 'min_xp': 35000, 'color': '#ec4899', 'icon': 'ph-trophy'},
        {'level': 13, 'name': 'Legend', 'code': 'LG', 'min_xp': 50000, 'color': '#f43f5e', 'icon': 'ph-fire'},
        {'level': 14, 'name': 'Mythic', 'code': 'MY', 'min_xp': 75000, 'color': '#ef4444', 'icon': 'ph-shooting-star'},
        {'level': 15, 'name': 'Immortal', 'code': 'IM', 'min_xp': 100000, 'color': '#f59e0b', 'icon': 'ph-sun', 'is_max_rank': True},
    ]
    
    for r in default_ranks:
        rank = CustomRank(
            user_id=user_id,
            level=r['level'],
            name=r['name'],
            code=r['code'],
            min_xp=r['min_xp'],
            color=r['color'],
            icon=r.get('icon'),
            is_max_rank=r.get('is_max_rank', False)
        )
        db.session.add(rank)
    
    # Create default daily tasks
    default_tasks = [
        {'name': 'Research', 'slug': 'research', 'icon': 'ph-magnifying-glass', 'color': '#3b82f6', 'xp_value': 15},
        {'name': 'Create', 'slug': 'create', 'icon': 'ph-pencil-line', 'color': '#22c55e', 'xp_value': 25},
        {'name': 'Engage', 'slug': 'engage', 'icon': 'ph-chat-circle', 'color': '#f97316', 'xp_value': 10},
        {'name': 'Learn', 'slug': 'learn', 'icon': 'ph-book-open', 'color': '#a855f7', 'xp_value': 10},
    ]
    
    for i, t in enumerate(default_tasks):
        task = UserDailyTask(
            user_id=user_id,
            name=t['name'],
            slug=t['slug'],
            icon=t['icon'],
            color=t['color'],
            xp_value=t['xp_value'],
            display_order=i
        )
        db.session.add(task)
    
    # Create default streak tracker
    streak = Streak(
        user_id=user_id,
        streak_type='daily_xp',
        current_count=0,
        longest_count=0
    )
    db.session.add(streak)
    
    # Create default achievements
    default_achievements = [
        # Getting Started
        {
            'name': 'First Step', 'slug': 'first_step', 'icon': 'ph-footprints',
            'color': '#22c55e', 'xp_reward': 25,
            'description': 'Complete your first task',
            'criteria': json.dumps({'type': 'task_complete', 'count': 1})
        },
        {
            'name': 'Early Bird', 'slug': 'early_bird', 'icon': 'ph-sun',
            'color': '#f59e0b', 'xp_reward': 50,
            'description': 'Log 5 entries before noon',
            'criteria': json.dumps({'type': 'custom', 'condition': 'morning_entries', 'count': 5})
        },
        # Streaks
        {
            'name': 'Consistency', 'slug': 'streak_7', 'icon': 'ph-fire',
            'color': '#ef4444', 'xp_reward': 100,
            'description': 'Maintain a 7-day streak',
            'criteria': json.dumps({'type': 'streak', 'min_days': 7})
        },
        {
            'name': 'Dedication', 'slug': 'streak_30', 'icon': 'ph-flame',
            'color': '#f97316', 'xp_reward': 500,
            'description': 'Maintain a 30-day streak',
            'criteria': json.dumps({'type': 'streak', 'min_days': 30})
        },
        {
            'name': 'Unstoppable', 'slug': 'streak_100', 'icon': 'ph-lightning',
            'color': '#eab308', 'xp_reward': 2000,
            'description': 'Maintain a 100-day streak',
            'criteria': json.dumps({'type': 'streak', 'min_days': 100})
        },
        # XP Milestones
        {
            'name': 'Rising Star', 'slug': 'xp_1000', 'icon': 'ph-star',
            'color': '#3b82f6', 'xp_reward': 100,
            'description': 'Earn 1,000 total XP',
            'criteria': json.dumps({'type': 'xp_total', 'threshold': 1000})
        },
        {
            'name': 'XP Hunter', 'slug': 'xp_10000', 'icon': 'ph-shooting-star',
            'color': '#6366f1', 'xp_reward': 500,
            'description': 'Earn 10,000 total XP',
            'criteria': json.dumps({'type': 'xp_total', 'threshold': 10000})
        },
        {
            'name': 'XP Legend', 'slug': 'xp_50000', 'icon': 'ph-sparkle',
            'color': '#a855f7', 'xp_reward': 2500,
            'description': 'Earn 50,000 total XP',
            'criteria': json.dumps({'type': 'xp_total', 'threshold': 50000})
        },
        # Daily Goals
        {
            'name': 'Goal Getter', 'slug': 'daily_goal_7', 'icon': 'ph-target',
            'color': '#14b8a6', 'xp_reward': 150,
            'description': 'Hit your daily goal 7 times',
            'criteria': json.dumps({'type': 'daily_goal', 'count': 7})
        },
        {
            'name': 'Overachiever', 'slug': 'daily_goal_30', 'icon': 'ph-trophy',
            'color': '#06b6d4', 'xp_reward': 750,
            'description': 'Hit your daily goal 30 times',
            'criteria': json.dumps({'type': 'daily_goal', 'count': 30})
        },
        # Content Creation (examples)
        {
            'name': 'Blogger', 'slug': 'blog_10', 'icon': 'ph-article',
            'color': '#3b82f6', 'xp_reward': 200,
            'description': 'Write 10 blog posts',
            'criteria': json.dumps({'type': 'total_count', 'trackable_slug': 'blog_post', 'threshold': 10})
        },
        {
            'name': 'YouTuber', 'slug': 'video_10', 'icon': 'ph-youtube-logo',
            'color': '#ef4444', 'xp_reward': 300,
            'description': 'Create 10 YouTube videos',
            'criteria': json.dumps({'type': 'total_count', 'trackable_slug': 'youtube_video', 'threshold': 10})
        },
        # Perfect Week
        {
            'name': 'Perfect Week', 'slug': 'perfect_week', 'icon': 'ph-calendar-check',
            'color': '#10b981', 'xp_reward': 250,
            'description': 'Complete all daily tasks for 7 days straight',
            'criteria': json.dumps({'type': 'perfect_week', 'count': 1})
        },
        # Exploration
        {
            'name': 'Explorer', 'slug': 'use_5_trackables', 'icon': 'ph-compass',
            'color': '#0ea5e9', 'xp_reward': 100,
            'description': 'Log entries in 5 different trackables',
            'criteria': json.dumps({'type': 'trackable_variety', 'count': 5})
        },
    ]
    
    for a in default_achievements:
        achievement = Achievement(
            user_id=user_id,
            name=a['name'],
            slug=a['slug'],
            icon=a['icon'],
            color=a['color'],
            xp_reward=a['xp_reward'],
            description=a['description'],
            criteria=a['criteria']
        )
        db.session.add(achievement)
    
    db.session.commit()
